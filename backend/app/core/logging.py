"""Centralised logging configuration.

Logs are emitted to stderr in a stable, machine-parseable format with a fixed
field order. When a request is being handled the correlation id is appended so
that logs can be filtered by ``request_id``.
"""

import logging
import sys

from app.config import settings


class RequestIdFilter(logging.Filter):
    """Attach the current request id (if any) to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        from app.core.context import get_request_id

        record.request_id = get_request_id()
        return True


_LOGGING_CONFIGURED = False


def setup_logging(level: str | None = None) -> None:
    """Configure root logging exactly once (idempotent)."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return
    _LOGGING_CONFIGURED = True

    root = logging.getLogger()
    root.setLevel((level or settings.log_level or "INFO").upper())

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | req=%(request_id)s | %(message)s"
        )
    )
    handler.addFilter(RequestIdFilter())
    root.handlers.clear()
    root.addHandler(handler)

    # Keep noisy third-party loggers at a sane level.
    for noisy in ("uvicorn.access", "httpx", "httpcore", "pdfminer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
