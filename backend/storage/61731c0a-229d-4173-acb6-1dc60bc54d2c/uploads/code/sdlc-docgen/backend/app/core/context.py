"""Per-request correlation context.

A request id is generated (or forwarded from a gateway-provided header) for
every request. It is exposed on responses via ``X-Request-ID`` and is attached
to all log lines emitted while the request is being handled, so a single
request can be traced end-to-end through the logs.
"""

import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def get_request_id() -> str:
    return request_id_var.get()
