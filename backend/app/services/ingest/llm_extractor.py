"""LLM-assisted detail extraction from ingested documents.

When a real model (e.g. Qwen served by vLLM) is reachable, the extractor asks it
to return structured JSON with the details the regex extractors cannot capture
(priority, verification method, interface fields, owners, due dates, ...). The
output is validated and merged with the deterministic extractors in
``pipeline.py``.

When no model is available the mock client reports no details and ingestion
falls back to the regex path, so offline behaviour is unchanged.
"""
import json
import re

from app.config import settings
from app.services.ingest.models import MoMRecord, ParsedDocument, RequirementExtract
from app.services.ingest.requirements_extractor import ID_RE, classify
from app.services.llm.client import get_llm_client

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

_TYPE_NORMALIZE = {
    "functional": "functional",
    "fr": "functional",
    "behavioural": "functional",
    "behavioral": "functional",
    "non_functional": "non_functional",
    "non-functional": "non_functional",
    "nonfunctional": "non_functional",
    "nfr": "non_functional",
    "interface": "interface",
    "constraint": "constraint",
    "constraints": "constraint",
}

# Requirement metadata fields the generator/renderer already understands
# (see generator._requirements_rows). Kept to this allowlist to avoid junk keys.
_EXTRA_FIELDS = (
    "priority",
    "verification",
    "measure",
    "target",
    "interface",
    "direction",
    "protocol",
    "module",
    "category",
    "status",
    "notes",
)

_SYSTEM_PROMPT = (
    "You are a requirements-analysis assistant for a defence R&D SDLC tool. "
    "Extract every requirement and engineering detail from the document you are given. "
    "Respond with ONLY a single JSON object and no surrounding prose."
)

_REQUIREMENTS_USER = (
    "Document type: {doc_type}.\n"
    "Extract ALL requirements. For each requirement include exactly the keys: "
    "req_id, text, type (one of functional | non_functional | interface | constraint), "
    "priority, verification (how the requirement will be tested or verified), "
    "and, when present in the source text: measure, target, interface, direction, "
    "protocol, module, plus a short context snippet. Do not invent requirement ids "
    "that are not written in the document.\n\n"
    'Return JSON like: {{"requirements": [{{"req_id": "REQ-0001", "text": "...", '
    '"type": "functional", "priority": "P1", "verification": "Test"}}]}}\n\n'
    "DOCUMENT TEXT:\n{document_text}"
)

_MOM_USER = (
    "Extract every record from this Minutes of Meeting. For each record include: "
    "kind (one of action_item | decision | requirement_change), text (the full "
    "record), owner and due date when present, and req_ids (the requirement ids "
    "mentioned, e.g. REQ-0001; empty list if none).\n\n"
    'Return JSON like: {{"mom_records": [{{"kind": "action_item", "text": "...", '
    '"owner": "...", "due": "...", "req_ids": ["REQ-0005"]}}]}}\n\n'
    "DOCUMENT TEXT:\n{document_text}"
)


def parse_json_block(text: str) -> dict | None:
    """Best-effort extraction of the single JSON object an LLM returned."""
    if not text:
        return None
    fenced = _FENCE_RE.search(text)
    candidate = fenced.group(1) if fenced else text
    match = _JSON_BLOCK_RE.search(candidate)
    if match is None:
        return None
    try:
        data = json.loads(match.group(0))
    except (TypeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def normalize_type(value, text: str) -> str:
    if not value:
        return classify(text)
    lowered = str(value).strip().lower().replace(" ", "_")
    if lowered in _TYPE_NORMALIZE:
        return _TYPE_NORMALIZE[lowered]
    return classify(text)


def normalize_requirements(raw, source: str) -> list[RequirementExtract]:
    """Validate and coerce the LLM's requirement list into RequirementExtract rows."""
    extracts: list[RequirementExtract] = []
    if not isinstance(raw, list):
        return extracts
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        req_id = str(entry.get("req_id", "")).strip()
        if not req_id or not ID_RE.fullmatch(req_id):
            continue
        text = str(entry.get("text", "")).strip()[:300]
        if not text:
            continue
        context = str(entry.get("context", "")).strip()[:400]
        extra = {key: str(entry[key]).strip() for key in _EXTRA_FIELDS if entry.get(key)}
        extracts.append(
            RequirementExtract(
                req_id=req_id,
                text=text,
                context=context,
                source=source,
                req_type=normalize_type(entry.get("type", entry.get("req_type", "")), text),
                extra=extra,
            )
        )
    return extracts


def normalize_mom_records(raw) -> list[MoMRecord]:
    records: list[MoMRecord] = []
    if not isinstance(raw, list):
        return records
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind", "")).strip()
        if kind not in ("action_item", "decision", "requirement_change"):
            continue
        text = str(entry.get("text", "")).strip()
        if not text:
            continue
        req_ids = [str(rid) for rid in entry.get("req_ids", []) if ID_RE.fullmatch(str(rid).strip())]
        records.append(
            MoMRecord(
                kind=kind,
                text=text,
                owner=str(entry["owner"]).strip() if entry.get("owner") else None,
                due=str(entry["due"]).strip() if entry.get("due") else None,
                req_ids=req_ids,
            )
        )
    return records


def llm_extract_details(parsed: ParsedDocument, doc_type: str) -> dict | None:
    """Return validated LLM-extracted details, or None when no model is available.

    Result shape: {"requirements": [RequirementExtract], "mom_records": [MoMRecord]}
    """
    if not settings.llm_extraction_enabled:
        return None
    client = get_llm_client()
    if client.name == "mock":
        return None

    document_text = parsed.text[: settings.llm_extraction_max_chars]
    if doc_type == "mom":
        user = _MOM_USER.format(document_text=document_text)
        key = "mom_records"
    else:
        user = _REQUIREMENTS_USER.format(doc_type=doc_type.upper(), document_text=document_text)
        key = "requirements"

    raw = client.complete(_SYSTEM_PROMPT, user)
    data = parse_json_block(raw)
    if data is None:
        return None

    result: dict = {}
    if key == "requirements":
        requirements = normalize_requirements(data.get("requirements"), doc_type)
        if requirements:
            result["requirements"] = requirements
    else:
        mom_records = normalize_mom_records(data.get("mom_records"))
        if mom_records:
            result["mom_records"] = mom_records
    return result or None
