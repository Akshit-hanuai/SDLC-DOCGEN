import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.requirement import Requirement, TraceabilityLink
from app.schemas.api import RequirementsResponse, TraceabilityResponse

router = APIRouter(tags=["requirements"])


@router.get("/projects/{project_id}/requirements", response_model=RequirementsResponse)
async def list_requirements(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> RequirementsResponse:
    result = await db.execute(
        select(Requirement)
        .where(Requirement.project_id == project_id)
        .order_by(Requirement.source, Requirement.req_id)
    )
    requirements = result.scalars().all()
    return RequirementsResponse(
        total=len(requirements),
        requirements=[
            {
                "req_id": r.req_id,
                "source": r.source,
                "req_type": r.req_type,
                "text": r.text,
                "context": (r.extra or {}).get("context", ""),
            }
            for r in requirements
        ],
    )


@router.get("/projects/{project_id}/traceability", response_model=TraceabilityResponse)
async def list_traceability(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> TraceabilityResponse:
    result = await db.execute(
        select(TraceabilityLink)
        .where(TraceabilityLink.project_id == project_id)
        .order_by(TraceabilityLink.from_req_id)
    )
    links = result.scalars().all()
    return TraceabilityResponse(
        total=len(links),
        links=[
            {
                "from": l.from_req_id,
                "to": l.to_req_id,
                "link_type": l.link_type,
                "source": l.source,
                "confidence": l.confidence,
            }
            for l in links
        ],
    )
