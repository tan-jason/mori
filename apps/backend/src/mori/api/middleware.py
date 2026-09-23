"""Request correlation and response security middleware."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint


async def security_headers_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    started_at = perf_counter()
    request.state.request_id = str(uuid4())
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    await structlog.get_logger("mori.http").ainfo(
        "request_completed",
        request_id=request.state.request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )
    return response
