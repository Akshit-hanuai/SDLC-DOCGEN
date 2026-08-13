import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import Requirement
from app.services.ingest.requirements_extractor import find_req_ids

REQ_REF_RE = re.compile(r"\b(?:REQ|SR|IR)-\d{3,4}(?:\.\d+)*\b")


def _referenced_ids(text: str) -> set[str]:
    return set(find_req_ids(text)) or set(REQ_REF_RE.findall(text))


async def check_compliance(
    session: AsyncSession,
    project_id,
    schema,
    content: dict,
) -> dict:
    registry_result = await session.execute(
        select(Requirement).where(Requirement.project_id == project_id)
    )
    registry = {r.req_id: r for r in registry_result.scalars().all()}

    sections_content = content.get("sections", {})
    all_text = _collect_text(sections_content)

    referenced = _referenced_ids(all_text)
    missing_refs = sorted(r for r in referenced if r not in registry)

    missing_sections = [s.id for s in schema.sections if s.required and not _section_filled(sections_content.get(s.id))]

    coverage_candidates = [
        r.req_id
        for r in registry.values()
        if r.req_type not in ("code_artifact", "test_case")
    ]
    uncovered = sorted(c for c in coverage_candidates if c not in referenced)

    passed = not missing_refs and not missing_sections
    return {
        "status": "pass" if passed else ("warn" if missing_refs else "pass"),
        "passed": passed,
        "missing_requirement_references": missing_refs,
        "missing_sections": missing_sections,
        "uncovered_requirements": uncovered,
        "referenced_ids": sorted(referenced),
        "registry_count": len(registry),
    }


def _collect_text(sections: dict) -> str:
    parts: list[str] = []
    for section in sections.values():
        if isinstance(section, dict):
            for value in section.values():
                if isinstance(value, str):
                    parts.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            parts.append(" ".join(str(v) for v in item.values()))
                elif isinstance(value, dict) and "text" in value:
                    parts.append(str(value["text"]))
        elif isinstance(section, str):
            parts.append(section)
    return "\n".join(parts)


def _section_filled(section) -> bool:
    if not section:
        return False
    if isinstance(section, str):
        return bool(section.strip())
    if isinstance(section, dict):
        for value in section.values():
            if isinstance(value, str) and value.strip():
                return True
            if isinstance(value, list) and value:
                return True
    return False
