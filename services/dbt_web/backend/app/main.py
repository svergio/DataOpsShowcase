from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.errors import DbtWebError, as_http_error
from app.state import AppState

app = FastAPI(title="dbt-web", version=settings.service_version)
app.include_router(v1_router)
app.state.ctx = AppState()


@app.exception_handler(DbtWebError)
async def dbt_web_error_handler(_: Request, exc: DbtWebError) -> JSONResponse:
    trace_id = str(uuid.uuid4())
    http_exc = as_http_error(exc, trace_id)
    return JSONResponse(status_code=http_exc.status_code, content=http_exc.detail)


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
