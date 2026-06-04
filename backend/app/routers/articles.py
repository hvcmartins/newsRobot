import math
from typing import Optional
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Article
from app.schemas.article import ArticleRead, ArticleListResponse

router = APIRouter()


@router.get("/", response_model=ArticleListResponse)
def list_articles(
    tenant_id: int,
    source_id: Optional[int] = None,
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    from_date: Optional[datetime.date] = None,
    to_date: Optional[datetime.date] = None,
    is_read: Optional[bool] = None,
    archived: Optional[bool] = None,   # None/False = pending queue; True = archive
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = (db.query(Article)
         .filter(Article.tenant_id == tenant_id,
                 Article.duplicate_of_id.is_(None)))

    if archived is True:
        q = q.filter(Article.archived_at.isnot(None))
    else:
        # Pending queue: only show fully-enriched articles
        q = q.filter(Article.archived_at.is_(None),
                     Article.ai_enriched == True)  # noqa: E712

    if source_id:
        q = q.filter(Article.source_id == source_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            (Article.title.ilike(like)) |
            (Article.excerpt.ilike(like)) |
            (Article.summary.ilike(like))
        )
    if category:
        q = q.filter(Article.category == category)
    if from_date:
        q = q.filter(Article.scraped_at >= datetime.datetime.combine(
            from_date, datetime.time.min))
    if to_date:
        q = q.filter(Article.scraped_at <= datetime.datetime.combine(
            to_date, datetime.time.max))
    if is_read is not None:
        q = q.filter(Article.is_read == is_read)

    total = q.count()
    items = (q.order_by(Article.category.asc().nullslast(),
                        Article.relevance_score.desc(),
                        Article.scraped_at.desc())
             .offset((page - 1) * size)
             .limit(size)
             .all())

    return ArticleListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 0,
    )


# ── Static-path routes (must come before /{article_id}) ──────────────────────

@router.get("/enrichment-status")
def enrichment_status(tenant_id: int, db: Session = Depends(get_db)):
    from app.services.ai.stats import get_stats
    from app.services.scraper.runner import is_enrichment_paused
    base = db.query(Article).filter(
        Article.tenant_id == tenant_id,
        Article.duplicate_of_id.is_(None),
        Article.archived_at.is_(None),
    )
    total = base.count()
    enriched = base.filter(Article.ai_enriched == True).count()
    stats = get_stats()
    return {
        "total": total,
        "enriched": enriched,
        "pending": total - enriched,
        "paused": is_enrichment_paused(tenant_id),
        "tokens_per_second": stats["tokens_per_second"],
        "seconds_per_article": stats["seconds_per_article"],
    }


@router.post("/enrich-stop")
def stop_enrichment(tenant_id: int):
    from app.services.scraper.runner import pause_tenant_enrichment
    pause_tenant_enrichment(tenant_id)
    return {"paused": True}


@router.post("/enrich")
def trigger_enrichment(
    tenant_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
):
    from app.services.scraper.runner import enrich_pending, resume_tenant_enrichment
    from app.services.ai.factory import get_ai_provider
    resume_tenant_enrichment(tenant_id)
    from app.services.ai.null import NullProvider
    try:
        ai = get_ai_provider()
    except Exception as exc:
        raise HTTPException(400, f"AI provider error: {exc}")
    if isinstance(ai, NullProvider):
        raise HTTPException(400, "No AI provider configured.")
    try:
        ai.summarize("test", "test")
    except Exception as exc:
        raise HTTPException(400, f"AI provider not responding: {exc}")
    if force:
        db.query(Article).filter(Article.tenant_id == tenant_id).update(
            {"ai_enriched": False, "relevance_score": 0,
             "relevance_reason": None, "summary": None, "category": None})
        db.commit()
    queued = enrich_pending(tenant_id, db)
    return {"queued": queued}


@router.patch("/read-all")
def mark_all_read(tenant_id: int, db: Session = Depends(get_db)):
    count = (db.query(Article)
             .filter(Article.tenant_id == tenant_id,
                     Article.is_read == False,
                     Article.archived_at.is_(None))
             .update({"is_read": True}))
    db.commit()
    return {"marked_read": count}


@router.get("/dashboard")
def dashboard(tenant_id: int, db: Session = Depends(get_db)):
    from app.models import EmailConfig, ScrapeRun, RunStatus
    from app.models.sent_digest import SentDigest

    today_start = datetime.datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0)

    scraped_today = (db.query(Article)
                     .filter(Article.tenant_id == tenant_id,
                             Article.scraped_at >= today_start)
                     .count())

    pending_count = (db.query(Article)
                     .filter(Article.tenant_id == tenant_id,
                             Article.archived_at.is_(None),
                             Article.duplicate_of_id.is_(None))
                     .count())

    week_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    recent_total = (db.query(Article)
                    .filter(Article.tenant_id == tenant_id,
                            Article.scraped_at >= week_ago,
                            Article.duplicate_of_id.is_(None))
                    .count())
    recent_enriched = (db.query(Article)
                       .filter(Article.tenant_id == tenant_id,
                               Article.scraped_at >= week_ago,
                               Article.ai_enriched == True)
                       .count())
    enrichment_rate = (round(recent_enriched / recent_total * 100)
                       if recent_total else None)

    last_digest = (db.query(SentDigest)
                   .filter_by(tenant_id=tenant_id)
                   .order_by(SentDigest.sent_at.desc())
                   .first())

    config: EmailConfig = (db.query(EmailConfig)
                           .filter_by(tenant_id=tenant_id)
                           .first())
    next_send = None
    if config and config.is_active and config.send_time:
        try:
            h, m = map(int, config.send_time.split(":"))
            now = datetime.datetime.utcnow()
            candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if candidate <= now:
                candidate += datetime.timedelta(days=1)
            next_send = candidate.isoformat()
        except Exception:
            pass

    recent_runs = (db.query(ScrapeRun)
                   .filter_by(tenant_id=tenant_id)
                   .order_by(ScrapeRun.started_at.desc())
                   .limit(20)
                   .all())
    runs_ok = sum(1 for r in recent_runs if r.status == RunStatus.success)
    runs_error = sum(1 for r in recent_runs if r.status == RunStatus.error)

    return {
        "scraped_today": scraped_today,
        "pending_count": pending_count,
        "enrichment_rate": enrichment_rate,
        "last_digest_at": last_digest.sent_at.isoformat() if last_digest else None,
        "last_digest_subject": last_digest.subject if last_digest else None,
        "next_send_at": next_send,
        "recent_runs_ok": runs_ok,
        "recent_runs_error": runs_error,
    }


# ── Reset endpoints ────────────────────────────────────────────────────────────

@router.delete("/reset/queue")
def reset_queue(tenant_id: int, db: Session = Depends(get_db)):
    count = (db.query(Article)
             .filter(Article.tenant_id == tenant_id,
                     Article.archived_at.is_(None))
             .delete())
    db.commit()
    return {"deleted": count}


@router.delete("/reset/archive")
def reset_archive(tenant_id: int, db: Session = Depends(get_db)):
    count = (db.query(Article)
             .filter(Article.tenant_id == tenant_id,
                     Article.archived_at.isnot(None))
             .delete())
    db.commit()
    return {"deleted": count}


@router.delete("/reset/scraped-urls")
def reset_scraped_urls(tenant_id: int, db: Session = Depends(get_db)):
    from app.models.scraped_url import ScrapedUrl
    count = (db.query(ScrapedUrl)
             .filter_by(tenant_id=tenant_id)
             .delete())
    db.commit()
    return {"deleted": count}


# ── Parameterised routes ──────────────────────────────────────────────────────

@router.get("/{article_id}", response_model=ArticleRead)
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return article


@router.patch("/{article_id}/read", response_model=ArticleRead)
def mark_read(article_id: int, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    article.is_read = True
    db.commit()
    db.refresh(article)
    return article


@router.post("/{article_id}/re-enrich")
def re_enrich_article(article_id: int, db: Session = Depends(get_db)):
    """Reset and re-queue AI enrichment for a single article."""
    import json
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    from app.models import Tenant
    from app.services.scraper.runner import _enrich_article, _enrich_executor
    tenant: Tenant = db.get(Tenant, article.tenant_id)
    article.ai_enriched = False
    article.relevance_score = 0.0
    article.relevance_reason = None
    article.summary = None
    article.category = None
    db.commit()
    accepted_langs = json.loads(tenant.accepted_languages or "[]") or None
    categories = json.loads(tenant.ai_categories or "[]") or None
    _enrich_executor.submit(
        _enrich_article, article_id,
        tenant.topic_profile, categories,
        accepted_langs, tenant.translation_language,
    )
    return {"queued": True}


@router.delete("/{article_id}", status_code=204)
def delete_article(article_id: int, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    db.delete(article)
    db.commit()
