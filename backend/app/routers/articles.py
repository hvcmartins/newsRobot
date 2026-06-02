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
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = (db.query(Article)
         .filter(Article.tenant_id == tenant_id,
                 Article.duplicate_of_id.is_(None)))

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
    items = (q.order_by(Article.relevance_score.desc(), Article.scraped_at.desc())
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
    """Return AI enrichment progress counts for the tenant's articles."""
    from app.services.ai.stats import get_stats
    from app.services.scraper.runner import is_enrichment_paused
    base = db.query(Article).filter(
        Article.tenant_id == tenant_id,
        Article.duplicate_of_id.is_(None),
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
    """Pause AI enrichment for this tenant. Queued tasks exit immediately."""
    from app.services.scraper.runner import pause_tenant_enrichment
    pause_tenant_enrichment(tenant_id)
    return {"paused": True}


@router.post("/enrich")
def trigger_enrichment(
    tenant_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
):
    """Queue AI enrichment for un-enriched articles.

    force=true resets ai_enriched on all articles first, so already-enriched
    articles are re-processed with the current AI provider and prompts.
    """
    from app.services.scraper.runner import enrich_pending, resume_tenant_enrichment
    from app.services.ai.factory import get_ai_provider
    resume_tenant_enrichment(tenant_id)
    from app.services.ai.null import NullProvider
    try:
        ai = get_ai_provider()
    except Exception as exc:
        raise HTTPException(400, f"AI provider error: {exc}")
    if isinstance(ai, NullProvider):
        raise HTTPException(400, "No AI provider configured. Go to AI Settings and set up a provider first.")
    # Quick smoke-test so we surface config problems before queuing hundreds of tasks
    try:
        ai.summarize("test", "test")
    except Exception as exc:
        raise HTTPException(400, f"AI provider is configured but not responding: {exc}")
    if force:
        reset_count = (db.query(Article)
                       .filter(Article.tenant_id == tenant_id)
                       .update({"ai_enriched": False, "relevance_score": 0,
                                "relevance_reason": None, "summary": None, "category": None}))
        db.commit()
    queued = enrich_pending(tenant_id, db)
    return {"queued": queued}


@router.patch("/read-all")
def mark_all_read(tenant_id: int, db: Session = Depends(get_db)):
    count = (db.query(Article)
             .filter(Article.tenant_id == tenant_id, Article.is_read == False)
             .update({"is_read": True}))
    db.commit()
    return {"marked_read": count}


@router.delete("/")
def clear_all_articles(tenant_id: int, db: Session = Depends(get_db)):
    """Delete every article for a tenant so the feed can be re-scraped cleanly."""
    count = db.query(Article).filter(Article.tenant_id == tenant_id).delete()
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


@router.delete("/{article_id}", status_code=204)
def delete_article(article_id: int, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    db.delete(article)
    db.commit()
