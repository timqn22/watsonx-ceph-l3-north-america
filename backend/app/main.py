"""FastAPI application factory.

Wires the API router, initializes the database, and starts the background
scraping scheduler on the lifespan startup event. CORS is open by default so
the browser extension can call the backend during the hackathon (tighten for
production).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import router
from .dashboard import router as dashboard_router
from .db import init_db
from .scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    shutdown_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TrackerAssist",
        version=__version__,
        description="AI-powered PR<->tracker linkage for Redmine + GitHub, "
        "powered by IBM Granite via watsonx.ai.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(dashboard_router)
    return app


app = create_app()
