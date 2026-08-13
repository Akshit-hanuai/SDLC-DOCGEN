import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document import Project
from app.schemas.api import EvalReport
from app.services.eval.evaluator import run_evaluation, write_scoring_sheet

router = APIRouter(tags=["evaluation"])

_REPORT_CACHE: dict[str, dict] = {}


@router.post("/projects/{project_id}/eval/run", response_model=EvalReport)
async def run_eval(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> EvalReport:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    report = await run_evaluation(db, project_id)
    _REPORT_CACHE[str(project_id)] = report
    return report


@router.get("/projects/{project_id}/eval/report", response_model=EvalReport)
async def get_eval_report(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> EvalReport:
    if str(project_id) in _REPORT_CACHE:
        return _REPORT_CACHE[str(project_id)]
    report = await run_evaluation(db, project_id)
    _REPORT_CACHE[str(project_id)] = report
    return report


@router.get("/projects/{project_id}/eval/scoring-sheet.csv")
async def scoring_sheet(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    report = await run_evaluation(db, project_id)
    path = write_scoring_sheet(report, f"/tmp/docgen-work/scoring_{project_id}.csv")
    return FileResponse(path, media_type="text/csv", filename=f"scoring_{project.name}.csv")
