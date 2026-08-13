import re
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.document import Project
from app.schemas.project import ProjectCreate, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"


def _rmdir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    limit: int = 100, 
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
) -> list[Project]:
    result = await db.execute(
        select(Project).order_by(Project.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)) -> Project:
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    slug = _slugify(project.name)
    # Core delete so the DB-level ON DELETE CASCADE handles related rows
    # (ORM delete would try to null out child FKs and fail on NOT NULL).
    await db.execute(delete(Project).where(Project.id == project_id))
    await db.commit()

    _rmdir(Path(settings.storage_root) / str(project.id))
    _rmdir(Path(settings.storage_root) / slug)
    _rmdir(Path(settings.git_repos_root) / f"{slug}.git")
    _rmdir(Path(settings.git_work_root) / slug)
