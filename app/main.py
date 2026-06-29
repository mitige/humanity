"""FastAPI application for Humanity.

FUNCTIONAL NOTE
---------------
This app serves the simulation API and the static UI. It exposes a FUNCTIONAL
simulation of processes associated with consciousness. The agent is not
conscious, sentient, or alive; introspective text is generated from internal
variables.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
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
