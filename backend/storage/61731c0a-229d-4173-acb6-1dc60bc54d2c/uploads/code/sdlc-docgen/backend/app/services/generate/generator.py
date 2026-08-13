import json
import re
import time
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, DocumentVersion, Project
from app.models.requirement import Requirement, TraceabilityLink
from app.models.source import SourceFile
from app.schemas.template import TemplateSchema
from app.services.audit import log_action
from app.services.generate.compliance import check_compliance
from app.services.generate.renderer import render_document
from app.services.git_service import commit_version
from app.services.ingest.models import Block
from app.services.llm.client import GROUNDING_MARKER, get_llm_client
from app.services.rag.chunker import chunk_blocks
from app.services.rag.vector_store import index_chunks, search
from app.services.template_store import template_store

DOC_SOURCE_MAP = {
    "SRS": ["sysrs", "mom", "irs"],
    "SDD": ["srs", "code", "sysrs", "mom"],
    "ICD": ["irs", "sysrs", "code"],
    "STP": ["srs", "sdd", "sysrs"],
    "STR": ["stp", "mom"],
}

_TITLE = {
    "SRS": "Software Requirements Specification",
    "SDD": "Software Design Description",
    "ICD": "Interface Control Document",
    "STP": "Software Test Plan",
    "STR": "Software Test Report",
}


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"


_MARKDOWN_INLINE = re.compile(
    r"\*\*(.+?)\*\*|__(.+?)__|(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)|`([^`]+)`"
)


def _clean_llm_text(text: str) -> str:
    """Strip Markdown markers from LLM output so stored JSON and DOCX render as plain text."""
    if not text:
        return text
    cleaned = []
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped in {"---", "***", "___"}:
            cleaned.append("")
            continue
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^\s*>\s?", "", line)
        line = _MARKDOWN_INLINE.sub(
            lambda m: next(g for g in m.groups() if g is not None), line
        )
        line = re.sub(r"^([-*+]\s+|\d+\.\s+)", "", line).rstrip()
        if re.match(r"^End of Section \d+\b", line.strip(), flags=re.IGNORECASE):
            continue
        cleaned.append(line)
    while cleaned and re.match(r"^Section \d+[:.]", cleaned[0].strip(), flags=re.IGNORECASE):
        cleaned.pop(0)
    out: list[str] = []
    blank = 0
    for line in cleaned:
        if not line.strip():
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(line)
    return "\n".join(out).strip()


async def generate_document(
    session: AsyncSession,
    project: Project,
    doc_type: str,
    user_id: uuid.UUID | None = None,
    regenerate_section: str | None = None,
    reviewer_comment: str | None = None,
    target_field: str | None = None,
    previous_version: DocumentVersion | None = None,
) -> tuple[Document, DocumentVersion, dict]:
    schema = template_store.get(doc_type.lower())
    if schema is None:
        raise ValueError(f"no template schema registered for doc_type={doc_type}")

    started = time.time()
    document = await get_or_create_document(session, project, doc_type)

    base_content = _content_from_previous(previous_version) if previous_version else None
    content, evidence = await _build_content(
        session,
        project,
        doc_type,
        schema,
        base_content,
        regenerate_section,
        reviewer_comment,
        target_field,
    )

    compliance = await check_compliance(session, project.id, schema, content)
    content["_evidence"] = evidence
    content["_compliance"] = compliance

    version = document.current_version + 1 if previous_version is None else previous_version.version + 1
    if regenerate_section is not None and previous_version is not None:
        version = previous_version.version + 1

    slug = _slugify(project.name)
    out_dir = Path(settings.storage_root) / slug / doc_type.lower()
    out_docx = out_dir / f"{doc_type}_v{version}.docx"
    out_docx = Path(
        render_document(
            schema, project.name, content, out_docx, classification="UNCLASSIFIED"
        )
    )
    out_json = out_dir / f"{doc_type}_v{version}.json"
    out_json.write_text(json.dumps(content, indent=2, default=str))

    source_versions = await _collect_source_versions(session, project.id)
    llm_client = get_llm_client()
    model_metadata = {
        "llm_client": llm_client.name,
        "model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "prompt_version": "1",
        "elapsed_s": round(time.time() - started, 2),
        "regenerate_section": regenerate_section,
    }

    version_row = DocumentVersion(
        document_id=document.id,
        version=version,
        content=content,
        rendered_docx_path=str(out_docx),
        status="draft",
        source_versions=source_versions,
        model_metadata=model_metadata,
        created_by=user_id,
    )
    session.add(version_row)
    document.current_version = version
    document.status = "draft"
    document.title = f"{doc_type} - {project.name}"
    await session.commit()
    await session.refresh(document)
    await session.refresh(version_row)

    files = {
        f"{doc_type}_v{version}.docx": str(out_docx),
        f"{doc_type}_v{version}.json": str(out_json),
        "compliance.json": str(_write_compliance(out_dir, version, compliance)),
    }
    sha = commit_version(project, document, version, files, {"source_versions": _version_tag(source_versions), "llm": llm_client.name})
    version_row.git_commit_sha = sha
    document.git_commit_sha = sha
    await session.commit()

    await index_document_content(session, project.id, doc_type, content)
    await log_action(
        session, project.id, user_id, "generate", "document_version", f"{document.id}:{version}",
        {"doc_type": doc_type, "llm": llm_client.name, "compliance": compliance["status"]},
    )

    await session.refresh(version_row)
    report = {
        "document_id": str(document.id),
        "doc_type": doc_type,
        "version": version,
        "compliance": compliance,
        "git_commit_sha": sha,
        "model_metadata": model_metadata,
        "rendered_path": str(out_docx),
    }
    return document, version_row, report


async def get_or_create_document(session: AsyncSession, project: Project, doc_type: str) -> Document:
    result = await session.execute(
        select(Document).where(Document.project_id == project.id, Document.doc_type == doc_type)
    )
    document = result.scalar_one_or_none()
    if document is None:
        document = Document(
            project_id=project.id,
            doc_type=doc_type,
            title=f"{doc_type} - {project.name}",
            template_name=doc_type.lower(),
            status="draft",
            current_version=0,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
    return document


def _content_from_previous(previous: DocumentVersion) -> dict:
    return {k: v for k, v in previous.content.items() if k not in ("_evidence", "_compliance")}


async def _build_content(
    session, project, doc_type, schema, base_content, regenerate_section, reviewer_comment, target_field
) -> tuple[dict, dict]:
    content = base_content or {"header": {}, "sections": {}}
    content.setdefault("header", {})
    content.setdefault("sections", {})
    for field_def in schema.header.document_control:
        content["header"].setdefault(field_def.field, field_def.default or "")
    evidence: dict = content.get("_evidence") or {}
    content["sections"] = content.get("sections", {})

    for section in schema.sections:
        if regenerate_section is not None and section.id != regenerate_section:
            continue
        content["sections"][section.id], section_evidence = await _build_section(
            session,
            project.id,
            doc_type,
            schema,
            section,
            reviewer_comment=reviewer_comment if section.id == regenerate_section else None,
            target_field=target_field if section.id == regenerate_section else None,
        )
        if section_evidence:
            evidence[section.id] = section_evidence

    content["_evidence"] = evidence
    return content, evidence


async def _build_section(
    session,
    project_id,
    doc_type,
    schema: TemplateSchema,
    section,
    reviewer_comment: str | None = None,
    target_field: str | None = None,
):
    if section.type == "requirements":
        rows, gaps = await _requirements_rows(session, project_id, doc_type, section)
        return {"requirements": rows, "gaps": gaps}, [r.get("requirement_id") or r.get("test_id") for r in rows]

    if section.type == "traceability_matrix":
        rows, uncovered = await _matrix_rows(session, project_id)
        return {"rows": rows, "uncovered": uncovered}, rows

    section_content = {}
    section_evidence = {}
    sources = section.data_sources or DOC_SOURCE_MAP.get(doc_type, [])
    for field in section.fields:
        if field.type == "table":
            rows, hits = await _generate_table_field(session, project_id, section, field, sources)
            section_content[field.id] = rows
            section_evidence[field.id] = hits
            continue
        text, hits = await _generate_text_field(
            session,
            project_id,
            doc_type,
            section,
            field,
            sources,
            reviewer_comment=reviewer_comment if field.id == target_field else None,
        )
        section_content[field.id] = text
        section_evidence[field.id] = hits
    return section_content, section_evidence


async def _generate_text_field(
    session, project_id, doc_type, section, field, sources, reviewer_comment: str | None = None
) -> tuple[str, list]:
    query = f"{section.title} {field.title}"
    hits = await search(session, project_id, query, settings.retriever_top_k, sources=sources)
    grounding = "\n".join(
        f"{h.source_file} | {h.heading} | {h.text.replace(chr(10), ' ')}" for h in hits
    )
    system = (
        f"You are a technical writer producing the {doc_type} for a defence R&D software project. "
        "Write strictly from the provided grounding chunks. Do not invent requirement IDs. "
        "Cite source requirement IDs (e.g. REQ-0001) whenever you rely on a source statement."
    )
    user = f"Section {section.id} '{section.title}', field '{field.title}'.\n"
    user += (field.instructions or section.instructions or "") + "\n"
    if reviewer_comment:
        user += (
            "A reviewer asked to add the following content. Elaborate and expand it into "
            "detailed, well-structured prose, weave it into the existing content of this field "
            "at the most natural point, and keep a consistent document tone. Do not simply quote it:\n"
            f"{reviewer_comment}\n"
        )
    user += f"\n{GROUNDING_MARKER}\n{grounding}"
    client = get_llm_client()
    text = _clean_llm_text(client.complete(system, user))
    evidence = [
        {"source": h.source_doc_type, "source_file": h.source_file, "heading": h.heading, "req_ids": h.req_ids}
        for h in hits
    ]
    return text, evidence


async def _generate_table_field(session, project_id, section, field, sources) -> tuple[list, list]:
    hits = await search(session, project_id, f"{section.title} {field.title}", settings.retriever_top_k, sources=sources)
    rows = []
    for hit in hits:
        row = {}
        for column in field.columns or []:
            row[column] = hit.req_ids[0] if column in ("requirement_id", "ref_id") and hit.req_ids else hit.heading
        rows.append(row)
    evidence = [
        {"source": h.source_doc_type, "source_file": h.source_file, "heading": h.heading, "req_ids": h.req_ids}
        for h in hits
    ]
    return rows[:10], evidence


async def _requirements_rows(session, project_id, doc_type, section) -> tuple[list, list]:
    if doc_type == "STP":
        return await _test_cases(session, project_id)
    if doc_type == "STR":
        return await _test_outcomes(session, project_id)
    req_filter = section.requirement_filter
    stmt = select(Requirement).where(Requirement.project_id == project_id)
    if req_filter and req_filter.req_type:
        stmt = stmt.where(Requirement.req_type == req_filter.req_type)
    result = await session.execute(stmt.order_by(Requirement.req_id))
    requirements = list(result.scalars().all())

    columns = (section.output.columns if section.output else None) or []
    rows = []
    for req in requirements:
        row = {"requirement_id": req.req_id, "requirement": req.text}
        if "source" in columns:
            row["source"] = req.source
        if "priority" in columns:
            row["priority"] = (req.extra or {}).get("priority", "")
        if "category" in columns:
            row["category"] = req.req_type
        if "verification" in columns:
            row["verification"] = "Test / inspection" if req.req_type != "interface" else "Interface test"
        if "interface" in columns:
            row["interface"] = (req.extra or {}).get("interface", "")
        if "direction" in columns:
            row["direction"] = (req.extra or {}).get("direction", "")
        if "protocol" in columns:
            row["protocol"] = (req.extra or {}).get("protocol", "")
        if "measure" in columns:
            row["measure"] = (req.extra or {}).get("measure", "")
        if "target" in columns:
            row["target"] = (req.extra or {}).get("target", "")
        if "artifact_id" in columns:
            row["artifact_id"] = req.req_id
        if "artifact" in columns:
            row["artifact"] = req.text
        if "artifact_type" in columns:
            row["artifact_type"] = req.req_type
        if "module" in columns:
            row["module"] = (req.extra or {}).get("module", "")
        if "description" in columns:
            row["description"] = req.text
        if "test_id" in columns:
            row["test_id"] = req.req_id
        if "title" in columns:
            row["title"] = req.text
        if "verifies" in columns:
            row["verifies"] = (req.extra or {}).get("verifies", "")
        if "procedure" in columns:
            row["procedure"] = (req.extra or {}).get("procedure", "")
        if "expected_result" in columns:
            row["expected_result"] = (req.extra or {}).get("expected_result", "")
        if "status" in columns:
            row["status"] = (req.extra or {}).get("status", "UNTESTED")
        if "notes" in columns:
            row["notes"] = (req.extra or {}).get("notes", "")
        rows.append(row)

    gaps = []
    if doc_type in ("SRS", "SDD", "ICD", "STP"):
        covered_ids = {r.get("requirement_id") for r in rows}
        # Get ALL requirements for this project (excluding generated artifacts)
        all_result = await session.execute(
            select(Requirement).where(
                Requirement.project_id == project_id,
                Requirement.req_type.notin_(["code_artifact", "test_case"]),
            )
        )
        all_reqs = all_result.scalars().all()
        gap_by_type: dict[str, list[str]] = {}
        for req in all_reqs:
            if req.req_id not in covered_ids:
                # Only flag as gap when req type matches section's filter
                req_filter = section.requirement_filter
                if req_filter and req_filter.req_type and req.req_type != req_filter.req_type:
                    continue
                category = req.req_type or "unknown"
                gap_by_type.setdefault(category, [])
                gap_by_type[category].append(
                    f"{req.req_id} [{req.source}]: {req.text[:120]}"
                )
        for category, items in sorted(gap_by_type.items()):
            gaps.append(f"--- {category.upper()} GAPS ({len(items)}) ---")
            gaps.extend(items)
    return rows, gaps


async def _test_cases(session, project_id) -> tuple[list, list]:
    result = await session.execute(
        select(Requirement).where(
            Requirement.project_id == project_id, Requirement.req_type == "test_case"
        )
    )
    existing = list(result.scalars().all())
    if existing:
        return _format_test_rows(existing), []

    result = await session.execute(
        select(Requirement).where(
            Requirement.project_id == project_id,
            Requirement.req_type.in_(["functional", "interface", "non_functional"]),
        )
    )
    candidates = list(result.scalars().all())
    rows = []
    for index, req in enumerate(candidates, start=1):
        test_id = f"TP-{index:04d}"
        row = {
            "test_id": test_id,
            "title": f"Verify {req.req_id}",
            "verifies": req.req_id,
            "procedure": f"1. Exercise the behaviour described in {req.req_id}. 2. Capture inputs and outputs.",
            "expected_result": f"{req.req_id} is satisfied as stated.",
        }
        rows.append(row)
        session.add(
            Requirement(
                req_id=test_id,
                project_id=project_id,
                source="stp",
                source_file="generated",
                req_type="test_case",
                text=row["title"],
                extra={"verifies": req.req_id, "procedure": row["procedure"], "expected_result": row["expected_result"], "status": "UNTESTED"},
            )
        )
        session.add(
            TraceabilityLink(
                project_id=project_id,
                from_req_id=test_id,
                to_req_id=req.req_id,
                link_type="verifies",
                source="generator",
                confidence=1.0,
            )
        )
    await session.commit()
    return rows, [r["test_id"] for r in rows]


def _format_test_rows(test_cases: list[Requirement]) -> tuple[list, list]:
    rows = []
    for test in test_cases:
        extra = test.extra or {}
        rows.append(
            {
                "test_id": test.req_id,
                "title": test.text,
                "verifies": extra.get("verifies", ""),
                "procedure": extra.get("procedure", ""),
                "expected_result": extra.get("expected_result", ""),
            }
        )
    return rows, [r["test_id"] for r in rows]


async def _test_outcomes(session, project_id) -> tuple[list, list]:
    result = await session.execute(
        select(Requirement).where(
            Requirement.project_id == project_id, Requirement.req_type == "test_case"
        )
    )
    test_cases = list(result.scalars().all())
    outcomes = await _mom_outcomes(session, project_id)
    rows = []
    for test in test_cases:
        extra = dict(test.extra or {})
        verifies = extra.get("verifies", "")
        status = outcomes.get(verifies, "UNTESTED")
        extra["status"] = status
        rows.append(
            {
                "test_id": test.req_id,
                "title": test.text,
                "status": status,
                "notes": extra.get("notes", "") or (f"Result recorded in MoM for {verifies}" if status != "UNTESTED" else ""),
            }
        )
    return rows, [r["test_id"] for r in rows]


async def _mom_outcomes(session, project_id) -> dict[str, str]:
    result = await session.execute(
        select(SourceFile).where(SourceFile.project_id == project_id, SourceFile.doc_type == "mom")
    )
    outcomes: dict[str, str] = {}
    for source_file in result.scalars().all():
        parsed = source_file.parsed_json or {}
        text = parsed.get("text", "")
        for line in text.splitlines():
            for req_id in re.findall(r"\b(?:REQ|SR)-\d{3,4}\b", line):
                lowered = line.upper()
                if "PASS" in lowered or "VERIFIED" in lowered:
                    outcomes[req_id] = "PASS"
                elif "FAIL" in lowered:
                    outcomes[req_id] = "FAIL"
    return outcomes


async def _matrix_rows(session, project_id) -> tuple[list, list]:
    result = await session.execute(
        select(TraceabilityLink).where(TraceabilityLink.project_id == project_id)
    )
    links = list(result.scalars().all())
    rows = [
        {"from": l.from_req_id, "to": l.to_req_id, "link_type": l.link_type, "confidence": l.confidence}
        for l in links
    ]
    result = await session.execute(
        select(Requirement).where(Requirement.project_id == project_id)
    )
    known = {r.req_id for r in result.scalars().all()}
    referenced = {l.from_req_id for l in links} | {l.to_req_id for l in links}
    uncovered = [rid for rid in sorted(known) if rid not in referenced]
    return rows, uncovered


async def _collect_source_versions(session, project_id) -> dict[str, str]:
    result = await session.execute(
        select(SourceFile).where(SourceFile.project_id == project_id)
    )
    versions = {}
    for source_file in result.scalars().all():
        versions[source_file.doc_type] = source_file.content_hash[:12]
    return versions


def _version_tag(source_versions: dict) -> str:
    return ";".join(f"{k}={v}" for k, v in sorted(source_versions.items()))


def _write_compliance(out_dir: Path, version: int, compliance: dict) -> str:
    path = out_dir / f"compliance_v{version}.json"
    path.write_text(json.dumps(compliance, indent=2))
    return str(path)


async def index_document_content(session: AsyncSession, project_id, doc_type: str, content: dict) -> int:
    schema = template_store.get(doc_type.lower())
    if schema is None:
        return 0
    blocks = []
    for section in schema.sections:
        section_content = content.get("sections", {}).get(section.id, {})
        text = _section_to_text(section_content)
        blocks.extend(
            chunk_blocks(
                [Block(heading=f"{section.id} {section.title}", level=1, text=text)],
                doc_type.lower(),
                f"{doc_type}.generated",
            )
        )
    return await index_chunks(session, project_id, blocks)


def _section_to_text(section_content) -> str:
    if isinstance(section_content, str):
        return section_content
    parts = []
    if isinstance(section_content, dict):
        for key, value in section_content.items():
            if key in ("_evidence", "_compliance"):
                continue
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        parts.append(" ".join(str(v) for v in item.values()))
            elif isinstance(value, dict):
                parts.append(str(value))
            else:
                parts.append(str(value))
    return "\n".join(parts)
