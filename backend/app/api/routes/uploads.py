import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.document import Project
from app.models.source import SourceFile
from app.schemas.api import IngestRunResponse, UploadResponse
from app.services.ingest import pipeline

router = APIRouter(tags=["ingestion"])

_MAX_BYTES = settings.max_upload_mb * 1024 * 1024
_UNSAFE_RE = re.compile(r"[\x00-\x1f\x7f]")


def _safe_name(filename: str | None) -> str:
    """Sanitise an uploaded filename: strip path separators and control chars."""
    name = (filename or "file").replace("\\", "/").split("/")[-1]
    name = _UNSAFE_RE.sub("", name).strip()
    if not name:
        name = "file"
    return name[:255]


def _detect_doc_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".zip"):
        return "code"
    if "mom" in lower or "meeting" in lower:
        return "mom"
    if "sysrs" in lower or "system requirement" in lower:
        return "sysrs"
    if "irs" in lower or "interface requirement" in lower:
        return "irs"
    return "doc"


@router.post("/projects/{project_id}/uploads", response_model=UploadResponse)
async def upload_files(
    project_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="maximum 20 files per upload request")

    dest_root = Path(settings.storage_root) / str(project_id) / "uploads"
    results = []
    for upload in files:
        raw = await upload.read()
        if len(raw) > _MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"file {upload.filename!r} exceeds the {settings.max_upload_mb} MB limit",
            )
        safe_name = _safe_name(upload.filename)
        doc_type = _detect_doc_type(safe_name)
        stored_path = pipeline.extract_upload(safe_name, raw, dest_root)
        if doc_type == "code":
            info = await pipeline.ingest_codebase(db, project_id, str(stored_path))
            results.append({"filename": safe_name, "doc_type": "code", **info})
        else:
            source_file = await pipeline.ingest_file(
                db, project_id, str(stored_path), safe_name, doc_type
            )
            results.append(
                {
                    "source_file_id": str(source_file.id),
                    "filename": source_file.filename,
                    "doc_type": source_file.doc_type,
                    "hash": source_file.content_hash[:12],
                }
            )
    return UploadResponse(project_id=str(project_id), ingested=results)


@router.post("/projects/{project_id}/ingest/run", response_model=IngestRunResponse)
async def run_ingestion(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> IngestRunResponse:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    result = await db.execute(
        select(SourceFile).where(SourceFile.project_id == project_id, SourceFile.parsed_json.is_(None))
    )
    pending = list(result.scalars().all())
    ingested = 0
    for source_file in pending:
        if source_file.doc_type == "code":
            await pipeline.ingest_codebase(db, project_id, source_file.path)
        else:
            await pipeline.ingest_file(db, project_id, source_file.path, source_file.filename, source_file.doc_type)
        ingested += 1
    return IngestRunResponse(project_id=str(project_id), ingested_files=ingested)
