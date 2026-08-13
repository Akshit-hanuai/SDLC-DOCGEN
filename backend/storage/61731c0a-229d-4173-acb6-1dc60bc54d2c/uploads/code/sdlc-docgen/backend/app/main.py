import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import audit, documents, eval, health, projects, requirements, review, templates, uploads
from app.config import settings
from app.core import RequestContextMiddleware, get_request_id, setup_logging
from app.database import engine

API_PREFIX = "/api/v1"

setup_logging()
logger = logging.getLogger(__name__)


async def _db_reachable() -> bool:
    from app.database import SessionLocal

    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up API v%s", settings.app_version)
    try:
        from app.services.llm.client import get_llm_client

        client = get_llm_client()
        logger.info("LLM client active: %s (mode=%s, model=%s)", client.name, settings.llm_mode, settings.llm_model)
    except Exception:  # noqa: BLE001 - startup must not fail because of an optional model
        logger.warning("Could not initialise LLM client", exc_info=True)
    if not await _db_reachable():
        logger.warning("Database not reachable at startup")
    else:
        logger.info("Database reachable")
    yield
    logger.info("Shutting down API, disposing DB engine...")
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Automated SDLC document generation API (FastAPI).",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = get_request_id()
        logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors()), "request_id": request_id},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        request_id = get_request_id()
        logger.error(
            "Unhandled error on %s %s (request_id=%s): %s",
            request.method,
            request.url.path,
            request_id,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected internal server error occurred.",
                "request_id": request_id,
            },
        )

    for router in (health, templates, projects, uploads, requirements, documents, review, eval, audit):
        app.include_router(router.router, prefix=API_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root():
        return {"app": settings.app_name, "version": settings.app_version, "docs": "/docs"}

    return app


app = create_app()
