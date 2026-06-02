import difflib
import json
import logging
import datetime
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Source, Article, ScrapeRun, RunStatus, SourceType, Tenant
from app.models.scraped_url import ScrapedUrl
from app.config import settings
from .rss_scraper import RssScraper
from .web_scraper import WebScraper
from .base import ScrapedArticle

logger = logging.getLogger(__name__)

_enrich_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="enrich")

_paused_tenants: set[int] = set()
_paused_lock = threading.Lock()


def pause_tenant_enrichment(tenant_id: int) -> None:
    with _paused_lock:
        _paused_tenants.add(tenant_id)
    logger.info("Enrichment paused for tenant %d", tenant_id)


def resume_tenant_enrichment(tenant_id: int) -> None:
    with _paused_lock:
        _paused_tenants.discard(tenant_id)
    logger.info("Enrichment resumed for tenant %d", tenant_id)


def is_enrichment_paused(tenant_id: int) -> bool:
    with _paused_lock:
        return tenant_id in _paused_tenants


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


def _record_scraped_url(db: Session, tenant_id: int, url: str) -> None:
    """Insert into scraped_urls using a savepoint so failure doesn't roll back the session."""
    try:
        with db.begin_nested():
            db.add(ScrapedUrl(tenant_id=tenant_id, url=url))
    except IntegrityError:
        pass  # Already recorded


def _is_url_seen(db: Session, tenant_id: int, url: str) -> bool:
    """Return True if the URL was already scraped for this tenant.

    Checks scraped_urls first, then falls back to the articles table so that
    articles ingested before the scraped_urls table existed are also recognised
    as duplicates (prevents IntegrityError cascade-rollbacks on the session).
    """
    if db.query(ScrapedUrl.id).filter_by(tenant_id=tenant_id, url=url).first():
        return True
    if db.query(Article.id).filter_by(tenant_id=tenant_id, url=url).first():
        return True
    return False


def _enrich_article(article_id: int, topic_profile: str | None,
                    categories: list[str] | None = None,
                    accepted_languages: list[str] | None = None,
                    translation_language: str | None = None) -> None:
    import logging as _logging
    ai_log = _logging.getLogger("app.services.ai.enrichment")

    from app.database import SessionLocal
    from app.services.ai.factory import get_ai_provider, wait_for_ai
    from app.services.ai.null import NullProvider

    if not wait_for_ai(timeout=600):
        ai_log.info("Discovery held the AI for 10 min — proceeding anyway")

    from app.services.ai.stats import record_article

    db = SessionLocal()
    t_article_start = time.monotonic()
    try:
        article = db.get(Article, article_id)
        if not article or article.ai_enriched:
            return

        if is_enrichment_paused(article.tenant_id):
            ai_log.debug("Enrichment paused for tenant %d — skipping article %d",
                         article.tenant_id, article_id)
            return

        ai = get_ai_provider()
        if isinstance(ai, NullProvider):
            return
        title_short = article.title[:70]

        try:
            result = ai.enrich_article(
                article.title, article.excerpt or "",
                topic_profile, categories or [],
                accepted_languages=accepted_languages,
                translation_language=translation_language,
            )
        except Exception as exc:
            ai_log.warning("enrich_article failed for '%s': %s", title_short, exc)
            return

        if topic_profile:
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

        if result.summary:
            article.summary = result.summary
        article.category = result.category
        ai_log.info("Enriched '%s' → %s", title_short, result.category or "—")

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
        age_days = tenant.max_article_age_days or settings.max_article_age_days
        max_age = datetime.timedelta(days=age_days)
        now = datetime.datetime.utcnow()

        for art in articles:
            # Age filter — applies to both RSS and web scraper when date is available
            if art.published_at:
                pub = art.published_at.replace(tzinfo=None)
                if (now - pub) > max_age:
                    logger.debug("Skipping old article (%s): '%s'",
                                 pub.date(), art.title[:70])
                    continue

            # Persistent deduplication via scraped_urls (survives archiving/deletion)
            if _is_url_seen(db, source.tenant_id, art.url):
                continue

            dup_id = _is_near_duplicate(art, recent, ai)
            score = _keyword_relevance(art, keywords)

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
            try:
                with db.begin_nested():
                    db.add(db_article)
            except IntegrityError:
                continue  # URL collision — _is_url_seen missed it; skip safely
            _record_scraped_url(db, source.tenant_id, art.url)
            new_count += 1
            new_article_ids.append(db_article.id)
            recent.append(db_article)
            if score >= 0.7:
                high_priority_new.append(db_article)

        db.commit()
        logger.info("Done '%s': %d new, %d already seen",
                    source.name, new_count, len(articles) - new_count)

        accepted_langs = json.loads(tenant.accepted_languages or "[]") or None
        tenant_categories = json.loads(tenant.ai_categories or "[]") or None
        if new_article_ids:
            logger.info("Queuing AI enrichment for %d article(s)", len(new_article_ids))
        for article_id in new_article_ids:
            _enrich_executor.submit(
                _enrich_article, article_id,
                tenant.topic_profile, tenant_categories,
                accepted_langs, tenant.translation_language,
            )

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
    tenant: Tenant = db.get(Tenant, tenant_id)
    topic_profile = tenant.topic_profile if tenant else None
    categories = json.loads(tenant.ai_categories or "[]") if tenant else None
    categories = categories or None
    accepted_langs = json.loads(tenant.accepted_languages or "[]") if tenant else None
    accepted_langs = accepted_langs or None
    translation_lang = tenant.translation_language if tenant else None

    pending = (db.query(Article)
               .filter(Article.tenant_id == tenant_id,
                       Article.ai_enriched.isnot(True),
                       Article.duplicate_of_id.is_(None))
               .all())
    count = 0
    for a in pending:
        _enrich_executor.submit(
            _enrich_article, a.id, topic_profile, categories,
            accepted_langs, translation_lang,
        )
        count += 1

    logger.info("Queued enrichment for %d pending articles (tenant %d)", count, tenant_id)
    return count
