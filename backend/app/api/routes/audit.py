import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.review import AuditLog
from app.schemas.api import AuditResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditResponse)
async def list_audit(
    project_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)
) -> AuditResponse:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)
    if project_id is not None:
        stmt = stmt.where(AuditLog.project_id == project_id)
    result = await db.execute(stmt)
    return AuditResponse(
        entries=[
            {
                "id": entry.id,
                "project_id": str(entry.project_id) if entry.project_id else None,
                "action": entry.action,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "details": entry.details,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            }
            for entry in result.scalars().all()
        ]
    )
