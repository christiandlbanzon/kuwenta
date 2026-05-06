"""APScheduler integration.

Two jobs:
- `monthly_insights_job`: runs at 02:00 Asia/Manila on the 1st of each month, generates
  last-month summaries for every user.
- `anomaly_scan_job`: runs daily at 03:00 Asia/Manila, scans every user for current-month
  spending anomalies vs a 3-month baseline.

Jobs are idempotent — re-running them produces no duplicates.

In v1 the scheduler runs in-process inside the same uvicorn worker. For multi-worker
deployments we'd need a Redis-backed APScheduler or a separate worker process.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import select

from app.db import async_session_maker
from app.models.user import User
from app.services import anomaly as anomaly_svc
from app.services import insights as insights_svc

log = logging.getLogger("kuwenta.scheduler")
TIMEZONE = "Asia/Manila"


async def monthly_insights_job() -> None:
    """For each user, generate last-month's summary if not already present."""
    log.info("monthly_insights_job started")
    async with async_session_maker() as session:
        users = (await session.exec(select(User))).all()
    count = 0
    errors = 0
    for user in users:
        try:
            async with async_session_maker() as session:
                insight = await insights_svc.generate_last_month_for_user(session, user)
                if insight:
                    count += 1
        except Exception:
            errors += 1
            log.exception("monthly_insights failed for user %s", user.id)
    log.info("monthly_insights_job done: %d generated, %d errors", count, errors)


async def anomaly_scan_job() -> None:
    """For each user, scan for current-month anomalies and persist."""
    log.info("anomaly_scan_job started")
    async with async_session_maker() as session:
        users = (await session.exec(select(User))).all()
    count = 0
    errors = 0
    for user in users:
        try:
            async with async_session_maker() as session:
                saved = await anomaly_svc.detect_and_persist(session, user)
                count += len(saved)
        except Exception:
            errors += 1
            log.exception("anomaly_scan failed for user %s", user.id)
    log.info("anomaly_scan_job done: %d new anomalies, %d errors", count, errors)


def start_scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=TIMEZONE)
    sched.add_job(
        monthly_insights_job,
        CronTrigger(day=1, hour=2, minute=0, timezone=TIMEZONE),
        id="monthly_insights",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    sched.add_job(
        anomaly_scan_job,
        CronTrigger(hour=3, minute=0, timezone=TIMEZONE),
        id="anomaly_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    sched.start()
    log.info("scheduler started; jobs: monthly_insights (1st 02:00), anomaly_scan (daily 03:00)")
    return sched
