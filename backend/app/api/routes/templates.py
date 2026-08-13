from fastapi import APIRouter, HTTPException

from app.schemas.api import TemplateListResponse, TemplateValidateResponse
from app.schemas.template import TemplateSchema
from app.services.template_store import template_store

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
async def list_templates() -> TemplateListResponse:
    return TemplateListResponse(templates=template_store.list_summaries())


@router.get("/validate", response_model=TemplateValidateResponse)
async def validate_templates() -> TemplateValidateResponse:
    errors = template_store.validate_all()
    return TemplateValidateResponse(valid=not errors, errors=errors)


@router.get("/{template_id}", response_model=TemplateSchema)
async def get_template(template_id: str) -> TemplateSchema:
    schema = template_store.get(template_id)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"template {template_id!r} not found")
    return schema.model_dump()
