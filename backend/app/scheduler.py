"""Periodic scraping via APScheduler.

Cadence (configurable):
  * open issues + open PRs  -- every SYNC_OPEN_MINUTES (default 15 min)
  * closed items drift catch -- every SYNC_CLOSED_HOURS (default 6 h)

On startup the open cycle runs once immediately so there is data to demo
without waiting for the first interval.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .config import get_settings
from .services.pipeline import run_closed_cycle, run_open_cycle

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    """Create, configure and start the background scheduler (once)."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_open_cycle,
        "interval",
        minutes=settings.sync_open_minutes,
        id="open_cycle",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_closed_cycle,
        "interval",
        hours=settings.sync_closed_hours,
        id="closed_cycle",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    # Kick one open cycle right away, off the request thread.
    scheduler.add_job(run_open_cycle, id="startup_open_cycle", replace_existing=True)
    logger.info(
        "Scheduler started: open every %sm, closed every %sh",
        settings.sync_open_minutes,
        settings.sync_closed_hours,
    )
    _scheduler = scheduler
    return scheduler


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
