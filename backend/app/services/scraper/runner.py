import difflib
import json
import logging
import datetime
import threading
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Source, Article, ScrapeRun, RunStatus, SourceType, Tenant
from app.config import settings
from .rss_scraper import RssScraper
from .web_scraper import WebScraper
from .base import ScrapedArticle

logger = logging.getLogger(__name__)


def _keyword_relevance(article: ScrapedArticle, keywords: list[str]) -> float:
    if not keywords:
        return 0.5
    text = f"{article.title} {article.excerpt or ''}".lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return round(hits / len(keywords), 3)


def _title_similarity(t1: str, t2: str) -> float:
    return difflib.SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


def _is_near_duplicate(article: ScrapedArticle, recent_articles: list[Article],
                        ai_provider) -> int | None:
    """Return the ID of the duplicate article, or None if unique."""
    for existing in recent_articles:
        ratio = _title_similarity(article.title, existing.title)
        if ratio >= 0.85:
            return existing.id
        if 0.60 <= ratio < 0.85:
            try:
                if ai_provider.are_duplicates(
                    article.title, article.excerpt or "",
                    existing.title, existing.excerpt or ""
                ):
                    return existing.id
            except Exception as exc:
                logger.warning("AI duplicate check failed: %s", exc)
    return None


def _enrich_article(article_id: int, topic_profile: str | None) -> None:
    """Run AI enrichment on a stored article in a background thread."""
    from app.database import SessionLocal
    from app.services.ai.factory import get_ai_provider

    db = SessionLocal()
    try:
        article = db.get(Article, article_id)
        if not article or article.ai_enriched:
            return

        ai = get_ai_provider()

        # Summary
        try:
            article.summary = ai.summarize(article.title, article.excerpt or "")
        except Exception as exc:
            logger.warning("Summarize failed for article %d: %s", article_id, exc)

        # Relevance (uses topic_profile if available)
        if topic_profile:
            try:
                result = ai.score_relevance(article.title, article.excerpt or "",
                                            topic_profile)
                article.relevance_score = result.score
                article.relevance_reason = result.reason
            except Exception as exc:
                logger.warning("Relevance scoring failed for article %d: %s",
                               article_id, exc)

        # Category
        try:
            article.category = ai.categorize(article.title, article.excerpt or "", [])
        except Exception as exc:
            logger.warning("Categorize failed for article %d: %s", article_id, exc)

        article.ai_enriched = True
        db.commit()
    except Exception as exc:
        logger.error("Enrichment failed for article %d: %s", article_id, exc)
    finally:
        db.close()


def run_source(source_id: int, db: Session) -> ScrapeRun:
    source: Source = db.get(Source, source_id)
    if not source or not source.is_active:
        raise ValueError(f"Source {source_id} not found or inactive")

    tenant: Tenant = db.get(Tenant, source.tenant_id)

    source_kws = json.loads(source.keywords or "[]")
    global_kws = json.loads(tenant.global_keywords or "[]")
    keywords = source_kws if source_kws else global_kws

    run = ScrapeRun(
        tenant_id=source.tenant_id,
        source_id=source.id,
        started_at=datetime.datetime.utcnow(),
        status=RunStatus.running,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        if source.type == SourceType.rss:
            scraper = RssScraper(source.url, source.name)
        else:
            scraper = WebScraper(source.url, source.name,
                                 source.css_selector or "article")

        articles = scraper.fetch()
        run.articles_found = len(articles)

        # Load recent articles for duplicate detection (last 24h)
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
        recent = (db.query(Article)
                  .filter(Article.tenant_id == source.tenant_id,
                          Article.scraped_at >= cutoff)
                  .all())

        from app.services.ai.factory import get_ai_provider
        ai = get_ai_provider()

        new_count = 0
        high_priority_new = []
        new_article_ids = []

        for art in articles:
            # URL deduplication
            existing = (db.query(Article)
                        .filter_by(tenant_id=source.tenant_id, url=art.url)
                        .first())
            if existing:
                continue

            # Near-duplicate detection
            dup_id = _is_near_duplicate(art, recent, ai)

            # Keyword-based relevance as initial score (AI enrichment runs async)
            score = _keyword_relevance(art, keywords)

            # If topic_profile set and AI enabled, apply relevance gate synchronously
            # for the gate decision (discard low-relevance articles)
            if tenant.topic_profile and settings.ai_enabled:
                try:
                    result = ai.score_relevance(art.title, art.excerpt or "",
                                                tenant.topic_profile)
                    score = result.score
                    if score < settings.ai_relevance_threshold:
                        logger.debug("Discarding low-relevance article: %s (score=%.2f)",
                                     art.title, score)
                        continue
                except Exception as exc:
                    logger.warning("Relevance gate failed, keeping article: %s", exc)

            db_article = Article(
                tenant_id=source.tenant_id,
                source_id=source.id,
                title=art.title,
                excerpt=art.excerpt,
                url=art.url,
                published_at=art.published_at,
                scraped_at=datetime.datetime.utcnow(),
                image_url=art.image_url,
                relevance_score=score,
                duplicate_of_id=dup_id,
            )
            db.add(db_article)
            try:
                db.flush()
                new_count += 1
                new_article_ids.append(db_article.id)
                recent.append(db_article)
                if score >= 0.7:
                    high_priority_new.append(db_article)
            except IntegrityError:
                db.rollback()

        db.commit()

        # Async AI enrichment — fire and forget
        for article_id in new_article_ids:
            t = threading.Thread(
                target=_enrich_article,
                args=(article_id, tenant.topic_profile),
                daemon=True,
            )
            t.start()

        source.last_scraped_at = datetime.datetime.utcnow()
        run.articles_new = new_count
        run.completed_at = datetime.datetime.utcnow()
        run.status = RunStatus.success
        db.commit()

        if high_priority_new:
            try:
                from app.services.email.sender import send_digest_if_configured
                send_digest_if_configured(
                    tenant_id=source.tenant_id,
                    articles=high_priority_new,
                    frequency="immediate",
                    db=db,
                )
            except Exception as exc:
                logger.warning("Immediate email send failed: %s", exc)

    except Exception as exc:
        logger.exception("Scrape failed for source %d", source_id)
        run.status = RunStatus.error
        run.error_message = str(exc)
        run.completed_at = datetime.datetime.utcnow()
        db.commit()

    return run


def run_all_sources(tenant_id: int, db: Session) -> list[ScrapeRun]:
    sources = (db.query(Source)
               .filter_by(tenant_id=tenant_id, is_active=True)
               .all())
    return [run_source(source.id, db) for source in sources]
