import uuid
import zipfile
from io import BytesIO
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import Requirement, TraceabilityLink
from app.models.source import SourceFile
from app.services.audit import log_action
from app.services.ingest.code_analyzer import analyze_code, file_hash
from app.services.ingest.linker import link_code_artifacts, link_extracts, link_mom
from app.services.ingest.llm_extractor import llm_extract_details
from app.services.ingest.models import Block, RequirementExtract
from app.services.ingest.mom_extractor import extract_mom
from app.services.ingest.parsers import parse_file
from app.services.ingest.requirements_extractor import extract_requirements
from app.services.rag.chunker import chunk_blocks
from app.services.rag.vector_store import index_chunks

DOC_TYPES = {"mom": "MoM", "sysrs": "SysRS", "irs": "IRS"}


async def ingest_file(
    session: AsyncSession,
    project_id: uuid.UUID,
    file_path: str,
    filename: str,
    doc_type: str,
    user_id: uuid.UUID | None = None,
) -> SourceFile:
    content_hash = file_hash(file_path)
    parsed = parse_file(file_path, doc_type)
    llm_details = llm_extract_details(parsed, doc_type)
    records: dict = {}
    mom_extracts: list[RequirementExtract] = []
    if doc_type == "mom":
        if llm_details and llm_details.get("mom_records"):
            mom_extracts = llm_details["mom_records"]
        else:
            mom_extracts = extract_mom(parsed, "mom")
        records["records"] = [r.__dict__ for r in mom_extracts]
        records["text"] = parsed.text

    source_file = SourceFile(
        project_id=project_id,
        filename=filename,
        doc_type=doc_type,
        path=str(file_path),
        content_hash=content_hash,
        parsed_json=records or {"text": parsed.text, "blocks": [b.__dict__ for b in parsed.blocks[:200]]},
        uploaded_by=user_id,
    )
    session.add(source_file)
    await session.commit()
    await session.refresh(source_file)

    extracts = extract_requirements(parsed.text, source=doc_type)
    if llm_details and llm_details.get("requirements"):
        extracts = _merge_extracts(extracts, llm_details["requirements"])
    if doc_type == "mom":
        existing = await _known_req_ids(session, project_id)
        mom_links, new_reqs = link_mom(mom_extracts, existing)
        extracts.extend(new_reqs)
    await _store_extracts(session, project_id, extracts)
    await _store_links(session, project_id, link_extracts(extracts))

    blocks = chunk_blocks(parsed.blocks, doc_type, filename)
    await index_chunks(session, project_id, blocks)

    audit_details = {"doc_type": doc_type, "requirements": len(extracts), "chunks": len(blocks)}
    if llm_details is not None:
        audit_details["llm"] = "enriched"
    await log_action(
        session, project_id, user_id, "ingest", "source_file", str(source_file.id), audit_details
    )
    return source_file


async def ingest_codebase(session: AsyncSession, project_id: uuid.UUID, repo_path: str, user_id: uuid.UUID | None = None) -> dict:
    analyses = analyze_code(repo_path)
    artifacts = [a for a in analyses for a in a.artifacts + a.endpoints + a.messages]
    await _store_code_artifacts(session, project_id, artifacts)

    code_text = "\n".join(
        f"{analysis.language}: {a.artifact_id} - {a.description}" for analysis in analyses for a in artifacts
    )
    source_file = SourceFile(
        project_id=project_id,
        filename="codebase",
        doc_type="code",
        path=str(repo_path),
        content_hash=file_hash(repo_path) if Path(repo_path).is_file() else str(hash(repo_path)),
        parsed_json={"analyses": [_serialize_analysis(a) for a in analyses]},
        uploaded_by=user_id,
    )
    session.add(source_file)
    await session.commit()
    await session.refresh(source_file)

    await _store_links(session, project_id, link_code_artifacts(analyses))

    code_blocks = []
    for path in sorted(Path(repo_path).rglob("*")):
        if path.is_file() and path.suffix in (".py", ".ts", ".tsx", ".js", ".java", ".proto"):
            parsed = parse_file(str(path), "code")
            code_blocks.extend(chunk_blocks(parsed.blocks, "code", str(path)))
    if not code_blocks:
        code_blocks = chunk_blocks(
            [Block(heading="code", level=1, text=code_text)], "code", "codebase"
        )
    await index_chunks(session, project_id, code_blocks)

    await log_action(
        session, project_id, user_id, "ingest", "codebase", str(source_file.id),
        {"artifacts": len(artifacts), "chunks": len(code_blocks)},
    )
    return {"source_file_id": str(source_file.id), "artifacts": len(artifacts), "chunks": len(code_blocks)}


async def _known_req_ids(session, project_id) -> set[str]:
    result = await session.execute(select(Requirement).where(Requirement.project_id == project_id))
    return {r.req_id for r in result.scalars().all()}


def _merge_extracts(base: list[RequirementExtract], llm: list[RequirementExtract]) -> list[RequirementExtract]:
    """Merge regex extracts with LLM extracts by req_id; LLM fills metadata gaps."""
    merged: dict[str, RequirementExtract] = {e.req_id: e for e in base}
    for entry in llm:
        existing = merged.get(entry.req_id)
        if existing is None:
            merged[entry.req_id] = entry
            continue
        merged[entry.req_id] = RequirementExtract(
            req_id=entry.req_id,
            text=entry.text or existing.text,
            context=entry.context or existing.context,
            source=existing.source,
            req_type=entry.req_type or existing.req_type,
            extra={**(existing.extra or {}), **(entry.extra or {})},
        )
    return list(merged.values())


async def _store_extracts(session, project_id, extracts: list[RequirementExtract]) -> None:
    known = await _known_req_ids(session, project_id)
    for extract in extracts:
        if extract.req_id in known:
            continue
        session.add(
            Requirement(
                req_id=extract.req_id,
                project_id=project_id,
                source=extract.source,
                source_file="ingested",
                req_type=extract.req_type,
                text=extract.text,
                extra={"context": extract.context, **(extract.extra or {})},
            )
        )
        known.add(extract.req_id)
    await session.commit()


async def _store_links(session, project_id, links) -> None:
    for link in links:
        session.add(
            TraceabilityLink(
                project_id=project_id,
                from_req_id=link.from_req_id,
                to_req_id=link.to_req_id,
                link_type=link.link_type,
                source=link.source,
                confidence=link.confidence,
            )
        )
    await session.commit()


async def _store_code_artifacts(session, project_id, artifacts) -> None:
    known = await _known_req_ids(session, project_id)
    for artifact in artifacts:
        if artifact.artifact_id in known:
            continue
        session.add(
            Requirement(
                req_id=artifact.artifact_id,
                project_id=project_id,
                source="code",
                source_file="codebase",
                req_type="code_artifact",
                text=artifact.description or artifact.name,
                extra={"name": artifact.name, "kind": artifact.kind, "module": artifact.module},
            )
        )
        known.add(artifact.artifact_id)
    await session.commit()


def _serialize_analysis(analysis) -> dict:
    return {
        "language": analysis.language,
        "modules": analysis.modules,
        "dependencies": analysis.dependencies,
        "artifacts": [a.__dict__ for a in analysis.artifacts],
        "endpoints": [a.__dict__ for a in analysis.endpoints],
        "messages": [a.__dict__ for a in analysis.messages],
    }


def extract_upload(filename: str, raw: bytes, dest_root: str | Path) -> Path:
    """Store an upload; zip codebase uploads get extracted. Returns the stored path."""
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    lower = filename.lower()
    if lower.endswith(".zip"):
        code_dir = dest_root / "code"
        code_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(BytesIO(raw)) as zf:
            for member in zf.infolist():
                target = (code_dir / member.filename).resolve()
                if not target.is_relative_to(code_dir.resolve()):
                    raise zipfile.BadZipFile(f"archive member escapes extraction dir: {member.filename!r}")
            zf.extractall(code_dir)
        return code_dir
    path = dest_root / filename
    path.write_bytes(raw)
    return path
