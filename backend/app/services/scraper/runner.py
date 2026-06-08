import difflib
import json
import logging
import datetime
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future
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

_paused_tenants: set[int] = set()   # enrichment pause
_paused_lock = threading.Lock()

_scrape_paused_tenants: set[int] = set()  # scraping pause
_scrape_paused_lock = threading.Lock()

# Track submitted (not-yet-started) futures per tenant so pause can cancel them
_tenant_futures: dict[int, list[Future]] = {}
_futures_lock = threading.Lock()

# Per-tenant scrape progress — updated by run_all_sources
_scrape_state: dict[int, dict] = {}
_scrape_lock = threading.Lock()

# Per-tenant active-scrape counter.  Enrichment tasks check this before their
# write phase so they don't compete for the SQLite write lock with the scraper.
_scraping_tenants: dict[int, int] = {}
_scraping_cond = threading.Condition(threading.Lock())


def get_scrape_status(tenant_id: int) -> dict:
    with _scrape_lock:
        return dict(_scrape_state.get(tenant_id, {
            "is_running": False, "total": 0, "done": 0, "articles_new": 0,
        }))


def _submit_enrich(tenant_id: int, *args, **kwargs) -> None:
    """Submit _enrich_article and track the future for cancellation on pause."""
    future = _enrich_executor.submit(_enrich_article, *args, **kwargs)
    with _futures_lock:
        _tenant_futures.setdefault(tenant_id, []).append(future)
    future.add_done_callback(lambda f: _remove_future(tenant_id, f))


def _remove_future(tenant_id: int, future: Future) -> None:
    with _futures_lock:
        lst = _tenant_futures.get(tenant_id)
        if lst:
            try:
                lst.remove(future)
            except ValueError:
                pass


def pause_tenant_enrichment(tenant_id: int) -> None:
    with _paused_lock:
        _paused_tenants.add(tenant_id)
    # Cancel every pending (not-yet-started) future for this tenant so the
    # queue drains immediately instead of task-by-task through Phase 1.
    with _futures_lock:
        futures = list(_tenant_futures.get(tenant_id, []))
    cancelled = sum(1 for f in futures if f.cancel())
    logger.info("Enrichment paused for tenant %d (%d pending tasks cancelled)", tenant_id, cancelled)


def resume_tenant_enrichment(tenant_id: int) -> None:
    with _paused_lock:
        _paused_tenants.discard(tenant_id)
    with _futures_lock:
        _tenant_futures.pop(tenant_id, None)
    logger.info("Enrichment resumed for tenant %d", tenant_id)


def is_enrichment_paused(tenant_id: int) -> bool:
    with _paused_lock:
        return tenant_id in _paused_tenants


def pause_tenant_scraping(tenant_id: int) -> None:
    with _scrape_paused_lock:
        _scrape_paused_tenants.add(tenant_id)
    logger.info("Scraping paused for tenant %d", tenant_id)


def resume_tenant_scraping(tenant_id: int) -> None:
    with _scrape_paused_lock:
        _scrape_paused_tenants.discard(tenant_id)
    logger.info("Scraping resumed for tenant %d", tenant_id)


def is_scraping_paused(tenant_id: int) -> bool:
    with _scrape_paused_lock:
        return tenant_id in _scrape_paused_tenants


def _begin_scraping(tenant_id: int) -> None:
    with _scraping_cond:
        _scraping_tenants[tenant_id] = _scraping_tenants.get(tenant_id, 0) + 1
    logger.info("Scraping started for tenant %d (active runs: %d)",
                tenant_id, _scraping_tenants[tenant_id])


def _end_scraping(tenant_id: int) -> None:
    with _scraping_cond:
        count = _scraping_tenants.get(tenant_id, 0)
        if count > 1:
            _scraping_tenants[tenant_id] = count - 1
        else:
            _scraping_tenants.pop(tenant_id, None)
        _scraping_cond.notify_all()
    logger.info("Scraping ended for tenant %d", tenant_id)


def _wait_for_scraping(tenant_id: int, timeout: float = 120) -> None:
    """Block until no scrape is active for this tenant (or timeout expires)."""
    with _scraping_cond:
        if not _scraping_cond.wait_for(
            lambda: not _scraping_tenants.get(tenant_id, 0), timeout=timeout
        ):
            logger.warning(
                "Enrichment for tenant %d waited %.0fs for scrape to finish — proceeding anyway",
                tenant_id, timeout,
            )


def _keyword_relevance(article: ScrapedArticle, keywords: list[str]) -> float:
    if not keywords:
        return 0.5
    text = f"{article.title} {article.excerpt or ''}".lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return round(hits / len(keywords), 3)


def _title_similarity(t1: str, t2: str) -> float:
    return difflib.SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


def _is_near_duplicate(article: ScrapedArticle, recent_articles: list[Article],
                        ai_provider, new_embedding: list[float] | None = None) -> int | None:
    import json as _json
    from app.services.ai.base import cosine_similarity

    for existing in recent_articles:
        # Prefer semantic similarity when both articles have embeddings
        existing_emb: list[float] | None = None
        if new_embedding and existing.title_embedding:
            try:
                existing_emb = _json.loads(existing.title_embedding)
            except Exception:
                pass

        if new_embedding and existing_emb:
            sim = cosine_similarity(new_embedding, existing_emb)
            if sim >= 0.92:
                logger.debug("Embedding duplicate (%.3f): '%s'", sim, article.title[:60])
                return existing.id
            if sim >= 0.80:
                try:
                    if ai_provider.are_duplicates(
                        article.title, article.excerpt or "",
                        existing.title, existing.excerpt or "",
                    ):
                        return existing.id
                except Exception as exc:
                    logger.warning("AI duplicate check failed: %s", exc)
            # sim < 0.80 → not a duplicate; no need to check string similarity too
        else:
            # Fallback: string similarity (no embeddings available)
            ratio = _title_similarity(article.title, existing.title)
            if ratio >= 0.85:
                return existing.id
            if 0.40 <= ratio < 0.85:
                try:
                    if ai_provider.are_duplicates(
                        article.title, article.excerpt or "",
                        existing.title, existing.excerpt or "",
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
    from app.services.scraper.base import fetch_og_image, resolve_article_url, _is_bad_redirect

    if not wait_for_ai(timeout=600):
        ai_log.info("Discovery held the AI for 10 min — proceeding anyway")

    from app.services.ai.stats import record_article

    # ── Phase 1: read article (short-lived session, closed before AI work) ────
    # Keeping the session open during AI calls (10-30 s) holds a SQLite
    # transaction open and blocks every other writer → "database is locked".
    db = SessionLocal()
    try:
        article = db.get(Article, article_id)
        if not article or article.ai_enriched:
            return
        if is_enrichment_paused(article.tenant_id):
            ai_log.debug("Enrichment paused for tenant %d — skipping article %d",
                         article.tenant_id, article_id)
            return
        # Snapshot the fields needed so the session can be closed immediately
        a_title = article.title
        a_excerpt = article.excerpt or ""
        a_url = article.url
        a_image_url = article.image_url
        a_embedding = article.title_embedding
        a_tenant_id = article.tenant_id
    finally:
        db.close()

    ai = get_ai_provider()
    if isinstance(ai, NullProvider):
        return

    # Re-check pause here: the task may have been queued before pause was set
    # and Phase 1 ran before it took effect.
    if is_enrichment_paused(a_tenant_id):
        ai_log.debug("Enrichment paused for tenant %d — skipping article %d (pre-AI check)",
                     a_tenant_id, article_id)
        return

    title_short = a_title[:70]
    t_article_start = time.monotonic()

    # ── Phase 2: AI + HTTP work (no DB session held) ──────────────────────────
    try:
        result = ai.enrich_article(
            a_title, a_excerpt,
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

    # Check pause after the AI call — the call itself can't be interrupted,
    # but we bail before the HTTP fetches and embedding that follow.
    if is_enrichment_paused(a_tenant_id):
        ai_log.debug("Enrichment paused for tenant %d — aborting post-AI steps for article %d",
                     a_tenant_id, article_id)
        return

    # Resolve Google News redirect to the real URL (no DB access)
    real_url = a_url
    if a_url and "news.google.com" in a_url:
        resolved = resolve_article_url(a_url)
        if resolved != a_url and not _is_bad_redirect(resolved):
            ai_log.debug("Resolved Google News URL for '%s': %s", title_short, resolved)
            real_url = resolved

    # Backfill missing image via og:image (HTTP fetch, no DB)
    new_image: str | None = a_image_url
    if not a_image_url and real_url:
        img = fetch_og_image(real_url)
        if img:
            new_image = img
            ai_log.debug("og:image found for '%s': %s", title_short, img)

    # Backfill embedding if missing (AI call, no DB)
    new_embedding_json: str | None = a_embedding
    if not a_embedding:
        try:
            emb = ai.embed(f"{a_title} {a_excerpt}"[:500])
            if emb:
                new_embedding_json = json.dumps(emb)
        except Exception:
            pass

    # ── Phase 3: write results (fresh short-lived session) ────────────────────
    # Wait for any active scrape to finish before opening a write transaction.
    # Concurrent scrape + enrichment writes both need the SQLite write lock;
    # the scrape's bulk-insert loop holds it for much longer than a single
    # enrichment write, so the enrichment task defers.
    _wait_for_scraping(a_tenant_id)

    db = SessionLocal()
    try:
        article = db.get(Article, article_id)
        if not article:
            return  # deleted between phases — nothing to do

        if topic_profile and result.score < 0.5:
            # Archive immediately rather than delete so the article is preserved
            # in history and won't be re-scraped on future runs.
            article.ai_enriched = True
            article.relevance_score = result.score
            article.relevance_reason = result.reason
            article.category = result.category
            article.archived_at = datetime.datetime.utcnow()
            db.commit()
            ai_log.info("Auto-archived low-relevance article (%.2f): '%s'",
                        result.score, title_short)
            return

        if topic_profile:
            article.relevance_score = result.score
            article.relevance_reason = result.reason
        if result.summary:
            article.summary = result.summary
        if result.translated_title:
            article.translated_title = result.translated_title
        article.category = result.category
        ai_log.info("Enriched '%s' → %s", title_short, result.category or "—")

        if real_url != a_url:
            article.url = real_url
        if new_image and not article.image_url:
            article.image_url = new_image
        if new_embedding_json and not article.title_embedding:
            article.title_embedding = new_embedding_json

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
    if is_scraping_paused(source.tenant_id):
        raise ValueError(f"Scraping is paused for tenant {source.tenant_id}")

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
    _begin_scraping(source.tenant_id)
    try:
        if source.type == SourceType.rss:
            scraper = RssScraper(source.url, source.name)
        else:
            scraper = WebScraper(source.url, source.name,
                                 source.css_selector or "article")

        articles = scraper.fetch()
        run.articles_found = len(articles)
        logger.info("Fetched %d article(s) from '%s'", len(articles), source.name)

        # 72h window catches the same story covered by different providers
        # over a multi-day news cycle. Exclude articles already flagged as
        # duplicates so we don't chain A→dup(A)→dup(dup(A)).
        dup_cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=72)
        recent = (db.query(Article)
                  .filter(Article.tenant_id == source.tenant_id,
                          Article.scraped_at >= dup_cutoff,
                          Article.duplicate_of_id.is_(None))
                  .all())

        from app.services.ai.factory import get_ai_provider
        ai = get_ai_provider()

        age_days = tenant.max_article_age_days or settings.max_article_age_days
        max_age = datetime.timedelta(days=age_days)
        now = datetime.datetime.utcnow()

        # ── Phase A: filter candidates (reads only, no write lock) ───────────
        candidates: list = []
        age_skipped = 0
        url_skipped = 0
        for art in articles:
            if art.published_at:
                pub = art.published_at.replace(tzinfo=None)
                if (now - pub) > max_age:
                    logger.debug("Skipping old article (%s): '%s'",
                                 pub.date(), art.title[:70])
                    age_skipped += 1
                    continue
            elif source.type == SourceType.scrape:
                logger.debug("Skipping undated web article: '%s'", art.title[:70])
                age_skipped += 1
                continue
            if _is_url_seen(db, source.tenant_id, art.url):
                url_skipped += 1
                continue
            candidates.append(art)

        # ── Phase B: pre-compute embeddings outside the write transaction ─────
        # ai.embed() inside the write loop holds the SQLite write lock for the
        # entire duration of N API calls (easily 30-60 s for large batches),
        # blocking every concurrent writer → "database is locked".
        pre_embeddings: list[list[float]] = []
        for art in candidates:
            emb: list[float] = []
            if not is_enrichment_paused(source.tenant_id):
                try:
                    emb = ai.embed(f"{art.title} {art.excerpt or ''}"[:500])
                except Exception as exc:
                    logger.debug("Embedding generation skipped: %s", exc)
            pre_embeddings.append(emb)

        # ── Phase C: dedup + write (fast; no embed calls inside write lock) ───
        new_count = 0
        high_priority_new = []
        new_article_ids = []

        for art, new_embedding in zip(candidates, pre_embeddings):
            if is_scraping_paused(source.tenant_id):
                logger.info("Scraping paused mid-run — stopping at article '%s'", art.title[:60])
                break
            dup_id = _is_near_duplicate(art, recent, ai, new_embedding)
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
                title_embedding=json.dumps(new_embedding) if new_embedding else None,
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
        parts = [f"{new_count} new"]
        if url_skipped:
            parts.append(f"{url_skipped} duplicate URL")
        if age_skipped:
            parts.append(f"{age_skipped} too old (>{age_days}d)")
        logger.info("Done '%s': %s", source.name, ", ".join(parts))

        accepted_langs = json.loads(tenant.accepted_languages or "[]") or None
        tenant_categories = json.loads(tenant.ai_categories or "[]") or None
        if new_article_ids:
            logger.info("Queuing AI enrichment for %d article(s)", len(new_article_ids))
        for article_id in new_article_ids:
            _submit_enrich(
                source.tenant_id,
                article_id,
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
    finally:
        _end_scraping(source.tenant_id)

    return run


def run_all_sources(tenant_id: int, db: Session) -> list[ScrapeRun]:
    sources = (db.query(Source)
               .filter_by(tenant_id=tenant_id, is_active=True)
               .all())
    with _scrape_lock:
        _scrape_state[tenant_id] = {
            "is_running": True, "total": len(sources), "done": 0, "articles_new": 0,
        }
    runs = []
    for source in sources:
        if is_scraping_paused(tenant_id):
            logger.info("Scraping paused — stopping after %d/%d sources for tenant %d",
                        len(runs), len(sources), tenant_id)
            break
        run = run_source(source.id, db)
        runs.append(run)
        with _scrape_lock:
            s = _scrape_state.get(tenant_id, {})
            s["done"] = s.get("done", 0) + 1
            s["articles_new"] = s.get("articles_new", 0) + (run.articles_new or 0)
            _scrape_state[tenant_id] = s
    with _scrape_lock:
        _scrape_state[tenant_id] = {
            "is_running": False,
            "total": len(sources),
            "done": len(sources),
            "articles_new": sum(r.articles_new or 0 for r in runs),
        }
    return runs


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
        _submit_enrich(
            tenant_id,
            a.id, topic_profile, categories,
            accepted_langs, translation_lang,
        )
        count += 1

    logger.info("Queued enrichment for %d pending articles (tenant %d)", count, tenant_id)
    return count
