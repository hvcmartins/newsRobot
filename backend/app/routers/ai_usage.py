import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.article import Article

router = APIRouter()


@router.get("/usage")
def ai_usage(
    view: str = Query("hour", pattern="^(minute|hour|day)$"),
    tenant_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """AI API usage stats.

    view=minute  → last 60 min, 1-min buckets
    view=hour    → last 24 h,  1-hour buckets
    view=day     → last 30 d,  1-day buckets
    """
    from app.services.ai.stats import get_usage_buckets, get_usage_today

    if view == "minute":
        buckets = get_usage_buckets(60, 60)
    elif view == "day":
        buckets = get_usage_buckets(86_400, 30)
    else:
        buckets = get_usage_buckets(3_600, 24)

    today_mem = get_usage_today()

    # DB-backed call count (persists across restarts) — enriched articles today
    today_start = datetime.datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0)
    q = db.query(Article).filter(
        Article.ai_enriched == True,
        Article.scraped_at >= today_start,
        Article.duplicate_of_id.is_(None),
    )
    if tenant_id:
        q = q.filter(Article.tenant_id == tenant_id)
    today_db_calls = q.count()

    return {
        "buckets": buckets,
        "today": today_mem,
        "today_db_calls": today_db_calls,
    }
