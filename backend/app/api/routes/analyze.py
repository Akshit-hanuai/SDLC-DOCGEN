from fastapi import APIRouter, File, HTTPException, UploadFile
from app.services.analyzer import ProjectAnalyzerService

router = APIRouter(prefix="/analyze", tags=["analyze"])

@router.post("/project")
async def analyze_project(file: UploadFile = File(...)):
    if not file.filename or not (file.filename.endswith(".zip") or file.filename.endswith(".tar.gz")):
        raise HTTPException(
            status_code=400,
            detail="Please upload a valid project zip archive (.zip)",
        )

    file_bytes = await file.read()
    if len(file_bytes) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size exceeds 100 MB cap.")

    service = ProjectAnalyzerService()
    try:
        analysis = await service.analyze_project_zip(file_bytes, file.filename)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Project analysis failed: {e}")
