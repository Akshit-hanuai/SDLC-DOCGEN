import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document import Document, DocumentVersion, Project
from app.models.review import Review
from app.schemas.api import (
    ActionResponse,
    ApproveResponse,
    RegenerateReport,
    ReviewResult,
    ReviewsResponse,
)
from app.services.review_service import (
    approve_document,
    get_user,
    regenerate_section,
    review_section,
    section_statuses,
    submit_for_review,
)

router = APIRouter(tags=["review"])


class ReviewRequest(BaseModel):
    username: str = Field(min_length=1)
    decision: str
    comment: str | None = None


class ApproveRequest(BaseModel):
    username: str = Field(min_length=1)


class RegenerateRequest(BaseModel):
    username: str | None = None
    comment: str = Field(min_length=1)
    target_field: str | None = None


async def _document_or_404(db: AsyncSession, document_id: uuid.UUID) -> Document:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return document


async def _version_or_404(db: AsyncSession, document_id: uuid.UUID, version: int) -> DocumentVersion:
    result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id, DocumentVersion.version == version
        )
    )
    version_row = result.scalar_one_or_none()
    if version_row is None:
        raise HTTPException(status_code=404, detail="version not found")
    return version_row


@router.post("/documents/{document_id}/submit", response_model=ActionResponse)
async def submit(
    document_id: uuid.UUID, payload: ApproveRequest, db: AsyncSession = Depends(get_db)
) -> ActionResponse:
    document = await _document_or_404(db, document_id)
    user = await get_user(db, payload.username)
    await submit_for_review(db, document, user.id)
    return ActionResponse(id=str(document.id), status=document.status)


@router.post(
    "/documents/{document_id}/versions/{version}/sections/{section_id}/review",
    response_model=ReviewResult,
)
async def review(
    document_id: uuid.UUID,
    version: int,
    section_id: str,
    payload: ReviewRequest,
    db: AsyncSession = Depends(get_db),
) -> ReviewResult:
    document = await _document_or_404(db, document_id)
    version_row = await _version_or_404(db, document_id, version)
    user = await get_user(db, payload.username)
    try:
        review_row = await review_section(
            db, document, version_row, section_id, user, payload.decision, payload.comment
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ReviewResult(
        id=str(review_row.id),
        decision=review_row.decision,
        section_id=review_row.section_id,
        document_status=document.status,
    )


@router.post(
    "/documents/{document_id}/versions/{version}/sections/{section_id}/regenerate",
    response_model=RegenerateReport,
)
async def regenerate(
    document_id: uuid.UUID,
    version: int,
    section_id: str,
    payload: RegenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> RegenerateReport:
    document = await _document_or_404(db, document_id)
    version_row = await _version_or_404(db, document_id, version)
    project = await db.get(Project, document.project_id)
    user = await get_user(db, payload.username) if payload.username else None
    new_version, report = await regenerate_section(
        db,
        project,
        document,
        version_row,
        section_id,
        payload.comment,
        user.id if user else None,
        target_field=payload.target_field,
    )
    return RegenerateReport(new_version=new_version.version, **report)


@router.post("/documents/{document_id}/approve", response_model=ApproveResponse)
async def approve(
    document_id: uuid.UUID, payload: ApproveRequest, db: AsyncSession = Depends(get_db)
) -> ApproveResponse:
    document = await _document_or_404(db, document_id)
    version_row = await _version_or_404(db, document_id, document.current_version)
    user = await get_user(db, payload.username)
    result = await approve_document(db, document, version_row, user)
    return ApproveResponse(id=str(document.id), **result)


@router.get("/documents/{document_id}/reviews", response_model=ReviewsResponse)
async def list_reviews(
    document_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ReviewsResponse:
    result = await db.execute(
        select(Review).where(Review.document_id == document_id).order_by(Review.created_at)
    )
    reviews = list(result.scalars().all())
    section_ids = sorted({r.section_id for r in reviews})
    statuses = section_statuses(reviews, section_ids)
    return ReviewsResponse(
        reviews=[
            {"version": r.version, "section_id": r.section_id, "decision": r.decision, "comment": r.comment}
            for r in reviews
        ],
        section_status=statuses,
    )
