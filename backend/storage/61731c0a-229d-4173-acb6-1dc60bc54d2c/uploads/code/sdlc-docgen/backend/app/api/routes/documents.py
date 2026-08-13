import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document import Document, DocumentVersion, Project
from app.schemas.api import (
    DiffResponse,
    DocumentDetail,
    DocumentsResponse,
    GenerateReport,
    VersionDetail,
)
from app.services.generate.generator import generate_document
from app.services.review_service import version_diff

router = APIRouter(tags=["documents"])

VALID_DOC_TYPES = {"SRS", "SDD", "ICD", "STP", "STR"}


class GenerateRequest(BaseModel):
    user_id: uuid.UUID | None = None
    section_id: str | None = None
    reviewer_comment: str | None = None


@router.get("/projects/{project_id}/documents", response_model=DocumentsResponse)
async def list_documents(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> DocumentsResponse:
    result = await db.execute(
        select(Document).where(Document.project_id == project_id).order_by(Document.doc_type)
    )
    return DocumentsResponse(
        documents=[
            {
                "id": str(d.id),
                "doc_type": d.doc_type,
                "title": d.title,
                "status": d.status,
                "current_version": d.current_version,
                "git_commit_sha": (d.git_commit_sha or "")[:10],
            }
            for d in result.scalars().all()
        ]
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> DocumentDetail:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    version_result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version.desc())
    )
    versions = version_result.scalars().all()
    return DocumentDetail(
        id=str(document.id),
        project_id=str(document.project_id),
        doc_type=document.doc_type,
        title=document.title,
        status=document.status,
        current_version=document.current_version,
        versions=[
            {
                "version": v.version,
                "status": v.status,
                "git_commit_sha": (v.git_commit_sha or "")[:10],
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "model_metadata": v.model_metadata,
            }
            for v in versions
        ],
    )


@router.get("/documents/{document_id}/versions/{version}", response_model=VersionDetail)
async def get_version(
    document_id: uuid.UUID, version: int, db: AsyncSession = Depends(get_db)
) -> VersionDetail:
    result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id, DocumentVersion.version == version
        )
    )
    version_row = result.scalar_one_or_none()
    if version_row is None:
        raise HTTPException(status_code=404, detail="version not found")
    return VersionDetail(
        version=version_row.version,
        content=version_row.content,
        source_versions=version_row.source_versions,
        model_metadata=version_row.model_metadata,
        git_commit_sha=version_row.git_commit_sha,
    )


@router.get("/documents/{document_id}/versions/{version}/diff", response_model=DiffResponse)
async def get_version_diff(
    document_id: uuid.UUID, version: int, db: AsyncSession = Depends(get_db)
) -> DiffResponse:
    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version.desc())
    )
    versions = list(result.scalars().all())
    current = next((v for v in versions if v.version == version), None)
    if current is None:
        raise HTTPException(status_code=404, detail="version not found")
    previous = next((v for v in versions if v.version < version), None)
    if previous is None:
        added = [{"section_id": s, "action": "added", "changed": True} for s in (current.content.get("sections") or {})]
        return DiffResponse(version=version, changes=added)
    return DiffResponse(version=version, changes=version_diff(previous.content, current.content))


@router.post("/projects/{project_id}/generate/{doc_type}", response_model=GenerateReport)
async def generate(
    project_id: uuid.UUID,
    doc_type: str,
    payload: GenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateReport:
    doc_type = doc_type.upper()
    if doc_type not in VALID_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of {sorted(VALID_DOC_TYPES)}")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    previous = None
    if payload.section_id:
        doc_result = await db.execute(
            select(Document).where(Document.project_id == project_id, Document.doc_type == doc_type)
        )
        existing_doc = doc_result.scalar_one_or_none()
        if existing_doc is not None:
            version_result = await db.execute(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == existing_doc.id)
                .order_by(DocumentVersion.version.desc())
                .limit(1)
            )
            previous = version_result.scalar_one_or_none()
    document, version, report = await generate_document(
        db,
        project,
        doc_type,
        user_id=payload.user_id,
        regenerate_section=payload.section_id,
        reviewer_comment=payload.reviewer_comment,
        previous_version=previous,
    )
    return GenerateReport(**report)


@router.get("/projects/{project_id}/documents/{doc_type}/download")
async def download_document(project_id: uuid.UUID, doc_type: str, db: AsyncSession = Depends(get_db)):
    doc_type = doc_type.upper()
    result = await db.execute(
        select(Document).where(Document.project_id == project_id, Document.doc_type == doc_type)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    version_result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version.desc())
        .limit(1)
    )
    version = version_result.scalar_one_or_none()
    if version is None or not version.rendered_docx_path:
        raise HTTPException(status_code=404, detail="no rendered document")
    return FileResponse(
        version.rendered_docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{doc_type}_v{version.version}.docx",
    )
