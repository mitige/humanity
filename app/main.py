"""FastAPI application for Humanity.

FUNCTIONAL NOTE
---------------
This app serves the simulation API and the static UI. It exposes a FUNCTIONAL
simulation of processes associated with consciousness. The agent is not
conscious, sentient, or alive; introspective text is generated from internal
variables.
"""
from __future__ import annotations

import math
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

# Directory holding the static front-end (index.html, app.js, styles.css).
_UI_DIR = Path(__file__).resolve().parent.parent / "ui"

app = FastAPI(
    title="Humanity",
    description=(
        "Functional simulation of processes associated with consciousness. "
        "The agent is not conscious, sentient, or alive."
    ),
    version="1.0.0",
)


def _json_safe_validation(value):
    """Make validation details serializable even for raw NaN/Infinity input."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe_validation(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe_validation(item) for item in value]
    return str(value)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    _request: Request, exc: RequestValidationError,
) -> JSONResponse:
    """Return a stable 422 instead of crashing while encoding hostile numbers."""
    return JSONResponse(
        status_code=422,
        content={"detail": _json_safe_validation(exc.errors())},
    )

# Permissive CORS for local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JSON API router.
app.include_router(router)

# Static UI mount (created if missing so startup never fails).
_UI_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/ui", StaticFiles(directory=str(_UI_DIR)), name="ui")


@app.get("/")
async def index() -> RedirectResponse:
    """Redirect the site root to the static UI entry point."""
    return RedirectResponse(url="/ui/index.html")
