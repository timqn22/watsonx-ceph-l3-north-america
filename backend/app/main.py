"""FastAPI application factory.

Wires the API router, initializes the database, and starts the background
scraping scheduler on the lifespan startup event.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from . import __version__
from .api import router
from .config import get_settings
from .dashboard import router as dashboard_router
from .db import init_db
from .limiter import limiter
from .recommend_page import router as recommend_router
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
    settings = get_settings()
    app = FastAPI(
        title="TrackerAssist",
        version=__version__,
        description="AI-powered PR<->tracker linkage for Redmine + GitHub, "
        "powered by IBM Granite via watsonx.ai.",
        lifespan=lifespan,
    )
    # CORS: restrict to the configured origins (extension + dashboard host).
    # Never open to * in production — the extension origin is known at deploy time.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "X-Api-Key"],
    )
    # Rate limiting: 120 req/min per IP by default; heavy endpoints set lower.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.include_router(router)
    app.include_router(dashboard_router)
    app.include_router(recommend_router)
    return app


app = create_app()
