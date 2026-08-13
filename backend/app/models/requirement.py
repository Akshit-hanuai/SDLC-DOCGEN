import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Requirement(Base):
    __tablename__ = "requirements"
    __table_args__ = (UniqueConstraint("project_id", "req_id", name="uq_project_req"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    req_id: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file: Mapped[str | None] = mapped_column(String(1024))
    source_version: Mapped[str | None] = mapped_column(String(128))
    req_type: Mapped[str | None] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    extra: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TraceabilityLink(Base):
    __tablename__ = "traceability_links"
    __table_args__ = (
        UniqueConstraint("project_id", "from_req_id", "to_req_id", "link_type", name="uq_trace_link"),
        ForeignKeyConstraint(
            ["project_id", "from_req_id"],
            ["requirements.project_id", "requirements.req_id"],
        ),
        ForeignKeyConstraint(
            ["project_id", "to_req_id"],
            ["requirements.project_id", "requirements.req_id"],
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    from_req_id: Mapped[str] = mapped_column(String(128), nullable=False)
    to_req_id: Mapped[str] = mapped_column(String(128), nullable=False)
    link_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    confidence: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
