import re

from app.config import settings
from app.services.ingest.models import RequirementExtract

ID_RE = re.compile(settings.req_id_pattern)

_TYPE_HINTS = {
    "performance": "non_functional",
    "reliability": "non_functional",
    "security": "non_functional",
    "maintainab": "non_functional",
    "interface": "interface",
    "constraint": "constraint",
    "mtbf": "non_functional",
}


def find_req_ids(text: str) -> list[str]:
    return sorted(set(m.group(0) for m in ID_RE.finditer(text)))


def extract_requirements(parsed_text: str, source: str, context_hint: str = "") -> list[RequirementExtract]:
    extracts: list[RequirementExtract] = []
    for match in ID_RE.finditer(parsed_text):
        req_id = match.group(0)
        after = parsed_text[match.end() : match.end() + 400]
        sentence = re.split(r"(?<=[.;:!?])\s", after.strip(), maxsplit=1)[0]
        text = (sentence or after.strip()).strip()[:300]
        if not text:
            text = "(no statement captured)"
        context = _surrounding(parsed_text, match.start(), context_hint)
        extracts.append(
            RequirementExtract(
                req_id=req_id,
                text=text,
                context=context,
                source=source,
                req_type=classify(text),
            )
        )
    return extracts


def classify(text: str) -> str:
    lowered = text.lower()
    for keyword, req_type in _TYPE_HINTS.items():
        if keyword in lowered:
            return req_type
    return "functional"


def _surrounding(text: str, pos: int, hint: str) -> str:
    start = max(0, pos - 120)
    end = min(len(text), pos + 200)
    snippet = " ".join(text[start:end].split())
    if hint:
        return f"[{hint}] {snippet}"
    return snippet
