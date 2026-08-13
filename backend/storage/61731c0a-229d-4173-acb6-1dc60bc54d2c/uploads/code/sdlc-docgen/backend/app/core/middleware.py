"""Request-context middleware.

Assigns a correlation id to every request, records an access-log line with the
response status and duration, and echoes the correlation id back to clients.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings

_HEADER = settings.request_id_header.upper()


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        from app.core.context import request_id_var

        supplied = request.headers.get(settings.request_id_header)
        request_id = supplied or uuid.uuid4().hex[:16]
        request_id_var.set(request_id)

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            _log_access(request, 500, time.perf_counter() - started, request_id)
            raise
        response.headers[_HEADER] = request_id
        _log_access(request, response.status_code, time.perf_counter() - started, request_id)
        return response


def _log_access(request: Request, status: int, elapsed: float, request_id: str) -> None:
    import logging

    logger = logging.getLogger("api.access")
    path = request.url.path
    if request.query_params:
        path = f"{path}?{request.query_params}"
    logger.info(
        "%s %s -> %s (%.1f ms) id=%s",
        request.method,
        path,
        status,
        elapsed * 1000,
        request_id,
    )
