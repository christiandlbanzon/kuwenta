"""Insights API — list existing insights and trigger generation on demand.

Background generation runs via APScheduler; these endpoints are for the dashboard
read path and ad-hoc generation (so the user can preview without waiting for the
1st-of-month cron).
"""

from datetime import date

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.core.deps import CurrentUser, SessionDep
from app.models.insight import Insight
from app.schemas.insights import GenerateMonthlySummaryRequest, InsightPublic
from app.services import anomaly as anomaly_svc
from app.services import insights as insights_svc
from app.tools._periods import _first_of_month, _last_of_month

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=list[InsightPublic])
async def list_insights(
    user: CurrentUser, session: SessionDep
) -> list[InsightPublic]:
    rows = (
        await session.exec(
            select(Insight)
            .where(Insight.user_id == user.id)
            .order_by(Insight.created_at.desc())  # type: ignore[attr-defined]
            .limit(50)
        )
    ).all()
    return [InsightPublic.model_validate(r, from_attributes=True) for r in rows]


@router.post("/monthly", response_model=InsightPublic)
async def generate_monthly(
    payload: GenerateMonthlySummaryRequest,
    user: CurrentUser,
    session: SessionDep,
) -> InsightPublic:
    """Generate (or fetch existing) monthly summary for the given month — defaults
    to last calendar month if year/month not specified."""
    if payload.year and payload.month:
        try:
            start = date(payload.year, payload.month, 1)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Bad month: {e}") from e
        end = _last_of_month(start)
        insight = await insights_svc.generate_for_period(
            session, user, period_start=start, period_end=end
        )
    else:
        insight = await insights_svc.generate_last_month_for_user(session, user)
    if not insight:
        raise HTTPException(
            status_code=404, detail="No transactions in that period to summarize."
        )
    return InsightPublic.model_validate(insight, from_attributes=True)


@router.post("/anomalies/scan", response_model=list[InsightPublic])
async def scan_anomalies(
    user: CurrentUser, session: SessionDep
) -> list[InsightPublic]:
    """Run anomaly detection now and persist any new flags as Insight rows."""
    saved = await anomaly_svc.detect_and_persist(session, user)
    return [InsightPublic.model_validate(i, from_attributes=True) for i in saved]
