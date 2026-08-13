import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import AuditLog


async def log_action(
    session: AsyncSession,
    project_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        project_id=project_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    session.add(entry)
    await session.commit()
    return entry
