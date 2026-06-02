import difflib
import json
import logging
import datetime
import time
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Source, Article, ScrapeRun, RunStatus, SourceType, Tenant
from app.config import settings
from .rss_scraper import RssScraper
from .web_scraper import WebScraper
from .base import ScrapedArticle

logger = logging.getLogger(__name__)

# Single enrichment worker: SQLite can't handle concurrent writers, and llamacpp
# already serializes inference via its own lock — extra threads only add contention.
_enrich_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="enrich")


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


def _enrich_article(article_id: int, topic_profile: str | None,
                    categories: list[str] | None = None) -> None:
    """Run AI enrichment on a stored article in a background thread."""
    import logging as _logging
    ai_log = _logging.getLogger("app.services.ai.enrichment")

    from app.database import SessionLocal
    from app.services.ai.factory import get_ai_provider, wait_for_ai
    from app.services.ai.null import NullProvider

    # Yield if source discovery is currently using the model
    if not wait_for_ai(timeout=600):
        ai_log.info("Discovery held the AI for 10 min — proceeding anyway")

    from app.services.ai.stats import record_article

    db = SessionLocal()
    t_article_start = time.monotonic()
    try:
        article = db.get(Article, article_id)
        if not article or article.ai_enriched:
            return

        ai = get_ai_provider()
        if isinstance(ai, NullProvider):
            # Real AI not configured yet — leave ai_enriched=False so articles
            # are picked up again once the user sets up an AI provider.
            return
        title_short = article.title[:70]

        # Step 1: Relevance check — run first so irrelevant articles are
        # discarded before spending tokens on summary or category.
        if topic_profile:
            try:
                result = ai.score_relevance(article.title, article.excerpt or "",
                                            topic_profile)
                ai_log.info("Relevance %.2f — '%s'%s",
                            result.score, title_short,
                            f" ({result.reason})" if result.reason else "")

                if result.score < 0.5:
                    db.query(Article).filter(Article.id == article_id).delete()
                    db.commit()
                    ai_log.info("Deleted low-relevance article (%.2f): '%s'",
                                result.score, title_short)
                    return

                article.relevance_score = result.score
                article.relevance_reason = result.reason
            except Exception as exc:
                ai_log.warning("Relevance scoring failed for '%s': %s", title_short, exc)

        # Step 2: Summary (only reached for relevant articles)
        ai_log.info("Summarising: '%s'", title_short)
        try:
            article.summary = ai.summarize(article.title, article.excerpt or "")
            ai_log.info("Summary done: '%s'", title_short)
        except Exception as exc:
            ai_log.warning("Summary failed for '%s': %s", title_short, exc)

        # Step 3: Category — use profile-derived categories when available
        try:
            article.category = ai.categorize(article.title, article.excerpt or "",
                                              categories or [])
            ai_log.info("Category: %s — '%s'", article.category, title_short)
        except Exception as exc:
            ai_log.warning("Categorize failed for '%s': %s", title_short, exc)

        article.ai_enriched = True
        db.commit()
        record_article(time.monotonic() - t_article_start)
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

    logger.info("Scraping '%s' [%s]", source.name, source.type.value.upper())

    try:
        if source.type == SourceType.rss:
            scraper = RssScraper(source.url, source.name)
        else:
            scraper = WebScraper(source.url, source.name,
                                 source.css_selector or "article")

        articles = scraper.fetch()
        run.articles_found = len(articles)
        logger.info("Fetched %d article(s) from '%s'", len(articles), source.name)

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
                        logger.info("Skipped (relevance %.2f): '%s'",
                                    score, art.title[:70])
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
        logger.info("Done '%s': %d new, %d already seen",
                    source.name, new_count, len(articles) - new_count)

        # Async AI enrichment — submit to bounded pool so DB connections
        # stay within the pool limit regardless of article count.
        tenant_categories = json.loads(tenant.ai_categories or "[]") or None
        if new_article_ids:
            logger.info("Queuing AI enrichment for %d article(s)", len(new_article_ids))
        for article_id in new_article_ids:
            _enrich_executor.submit(_enrich_article, article_id,
                                    tenant.topic_profile, tenant_categories)

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


def enrich_pending(tenant_id: int, db: Session) -> int:
    """Queue AI enrichment for every un-enriched article of a tenant.

    Safe to call at any time — articles already enriched are skipped inside
    _enrich_article. Returns the number of articles queued.
    """
    tenant: Tenant = db.get(Tenant, tenant_id)
    topic_profile = tenant.topic_profile if tenant else None
    categories = json.loads(tenant.ai_categories or "[]") if tenant else None
    categories = categories or None

    # Use isnot(True) rather than == False so that NULL values (legacy rows
    # added before the column existed) are also picked up.
    pending = (db.query(Article)
               .filter(Article.tenant_id == tenant_id,
                       Article.ai_enriched.isnot(True),
                       Article.duplicate_of_id.is_(None))
               .all())
    count = 0
    for a in pending:
        _enrich_executor.submit(_enrich_article, a.id, topic_profile, categories)
        count += 1

    logger.info("Queued enrichment for %d pending articles (tenant %d)", count, tenant_id)
    return count
