import logging
import uuid
import datetime as _dt
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models import CatalogSource, Source
from app.schemas.catalog_source import (CatalogSourceCreate, CatalogSourceRead,
                                         CatalogSourceUpdate)
from app.schemas.source import SourceRead

router = APIRouter()

# ── In-memory discovery job store ─────────────────────────────────────────────
# Keeps the last 50 jobs. Each entry: {status, sources?, error?, started_at}
_discovery_jobs: dict[str, dict] = {}

_MAX_JOBS = 50


# ── Static-path routes first ─────────────────────────────────────────────────
# All literal-segment routes MUST be registered before /{catalog_id} routes,
# otherwise Starlette matches e.g. POST /discover against /{catalog_id}/add.

@router.get("/", response_model=list[CatalogSourceRead])
def list_catalog(
    category: Optional[str] = None,
    language: Optional[str] = None,
    country: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(CatalogSource)
    if category:
        query = query.filter(CatalogSource.category == category)
    if language:
        query = query.filter(CatalogSource.language == language)
    if country:
        query = query.filter(CatalogSource.country == country)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (CatalogSource.name.ilike(like)) |
            (CatalogSource.description.ilike(like))
        )
    return query.order_by(CatalogSource.category, CatalogSource.name).all()


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    rows = db.query(CatalogSource.category).distinct().order_by(CatalogSource.category).all()
    return [r[0] for r in rows]


@router.post("/", response_model=CatalogSourceRead, status_code=201)
def create_catalog_source(data: CatalogSourceCreate, db: Session = Depends(get_db)):
    if db.query(CatalogSource).filter_by(url=data.url).first():
        raise HTTPException(400, "URL already exists in catalog")
    cs = CatalogSource(**data.model_dump())
    db.add(cs)
    db.commit()
    db.refresh(cs)
    return cs


def _check_url(url: str) -> tuple[bool, str | None]:
    """Return (reachable, corrected_url_or_None).

    If the given URL fails, try common feed paths on the same domain so
    hallucinated AI URLs can be auto-corrected to a working feed.
    """
    import httpx
    from urllib.parse import urlparse

    _FEED_PATHS = ["/feed", "/rss.xml", "/feed.xml", "/atom.xml", "/rss",
                   "/news/rss", "/feeds/all.rss.xml"]
    _FEED_CONTENT_TYPES = ("rss", "atom", "xml", "feed")

    def _is_feed_response(r) -> bool:
        ct = r.headers.get("content-type", "").lower()
        return any(t in ct for t in _FEED_CONTENT_TYPES) or r.status_code < 400

    try:
        with httpx.Client(timeout=4, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (compatible; NewsRobot/1.0)"}) as c:
            try:
                r = c.head(url)
                if r.status_code < 400:
                    return True, None
            except Exception:
                pass

            # Original URL failed — check domain is alive before trying fallback paths
            base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            try:
                probe = c.head(base, timeout=3)
                if probe.status_code >= 400:
                    return False, None   # domain dead, skip fallbacks
            except Exception:
                return False, None       # domain unreachable

            for path in _FEED_PATHS:
                candidate = base + path
                if candidate == url:
                    continue
                try:
                    r = c.head(candidate, timeout=3)
                    if _is_feed_response(r):
                        return True, candidate
                except Exception:
                    continue
    except Exception:
        pass
    return False, None


def _run_discovery_job(job_id: str, tenant_id: int, topic_profile: str,
                       tenant_name: str,
                       accepted_languages: list[str] | None = None) -> None:
    """Background worker — runs AI discovery + web search + URL validation."""
    from app.database import SessionLocal
    from app.services.ai.factory import get_ai_provider, pause_enrichment, resume_enrichment

    pause_enrichment()
    db = SessionLocal()
    try:
        suggestions: list[dict] = []
        ai_error: Exception | None = None

        ai = get_ai_provider(db)
        try:
            suggestions = ai.discover_sources(topic_profile, accepted_languages)
        except Exception as exc:
            logger.error("AI source discovery failed: %s", exc)
            ai_error = exc

        # Augment with web search (failure is acceptable)
        try:
            from app.services.feed_search import web_search_feeds
            web_feeds = web_search_feeds(topic_profile, accepted_languages=accepted_languages)
            ai_urls = {s["url"] for s in suggestions}
            new_from_web = [f for f in web_feeds if f["url"] not in ai_urls]
            if new_from_web:
                logger.info("Web search added %d sources for '%s'", len(new_from_web), tenant_name)
                suggestions = suggestions + new_from_web
        except Exception as exc:
            logger.warning("Web feed search failed (non-critical): %s", exc)

        if not suggestions:
            if ai_error:
                _discovery_jobs[job_id] = {"status": "error",
                                           "error": f"AI source discovery failed: {ai_error}"}
            else:
                _discovery_jobs[job_id] = {"status": "done", "sources": []}
            return

        # URL validation in parallel
        tenant_source_urls = {s.url for s in db.query(Source).filter_by(tenant_id=tenant_id).all()}
        catalog_urls = {c.url for c in db.query(CatalogSource).all()}

        with ThreadPoolExecutor(max_workers=min(len(suggestions), 10)) as pool:
            futures = {pool.submit(_check_url, s["url"]): i for i, s in enumerate(suggestions)}
            check_results: dict[int, tuple[bool, str | None]] = {}
            try:
                for future in as_completed(futures, timeout=20):
                    idx = futures[future]
                    try:
                        check_results[idx] = future.result()
                    except Exception:
                        check_results[idx] = (False, None)
            except FuturesTimeout:
                logger.warning("URL validation timed out; %d/%d completed",
                               len(check_results), len(futures))
                for idx in futures.values():
                    check_results.setdefault(idx, (False, None))

        result = []
        for i, s in enumerate(suggestions):
            ok, corrected_url = check_results.get(i, (False, None))
            url = corrected_url or s["url"]
            result.append({
                **s,
                "url": url,
                "reachable": ok,
                "already_in_feed": url in tenant_source_urls or s["url"] in tenant_source_urls,
                "in_catalog": url in catalog_urls or s["url"] in catalog_urls,
                "url_corrected": corrected_url is not None,
            })

        result.sort(key=lambda x: (0 if x["reachable"] else 1))
        logger.info("Source discovery: %d reachable / %d total for '%s'",
                    sum(1 for s in result if s["reachable"]), len(result), tenant_name)
        _discovery_jobs[job_id] = {"status": "done", "sources": result}

    except Exception as exc:
        logger.error("Discovery job %s crashed: %s", job_id, exc)
        _discovery_jobs[job_id] = {"status": "error", "error": str(exc)}
    finally:
        db.close()
        resume_enrichment()


@router.post("/discover")
def discover_sources(tenant_id: int, background_tasks: BackgroundTasks,
                     db: Session = Depends(get_db)):
    """Start an async source discovery job. Returns a job_id immediately.
    Poll GET /discover?job_id=<id> for status/results."""
    from app.models import Tenant
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if not tenant.topic_profile:
        raise HTTPException(400, "Set an AI Topic Profile first before discovering sources.")

    from app.services.ai.factory import get_ai_provider
    from app.services.ai.null import NullProvider
    if isinstance(get_ai_provider(), NullProvider):
        raise HTTPException(400, "Configure an AI provider in AI Settings to use source discovery.")

    job_id = uuid.uuid4().hex[:12]
    _discovery_jobs[job_id] = {
        "status": "running",
        "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }

    # Evict oldest jobs beyond the cap
    if len(_discovery_jobs) > _MAX_JOBS:
        oldest = sorted(_discovery_jobs, key=lambda k: _discovery_jobs[k].get("started_at", ""))[
            :len(_discovery_jobs) - _MAX_JOBS
        ]
        for k in oldest:
            _discovery_jobs.pop(k, None)

    import json as _json
    accepted_langs = _json.loads(tenant.accepted_languages or "[]") or None
    logger.info("Source discovery job %s started for '%s' (languages=%s)",
                job_id, tenant.name, accepted_langs)
    background_tasks.add_task(
        _run_discovery_job, job_id, tenant_id, tenant.topic_profile,
        tenant.name, accepted_langs
    )
    return {"job_id": job_id, "status": "running"}


@router.get("/discover")
def get_discover_status(job_id: str):
    """Poll discovery job status. Returns {status, sources?} or {status, error?}."""
    job = _discovery_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Discovery job not found or expired")
    return job


@router.post("/discover/add", response_model=SourceRead, status_code=201)
def add_discovered_source(tenant_id: int, data: dict, db: Session = Depends(get_db)):
    """Add a discovered source (from AI discovery) directly to the tenant feed."""
    from app.models import Source, SourceType
    if not data.get("url") or not data.get("name"):
        raise HTTPException(400, "name and url are required")
    existing = db.query(Source).filter_by(tenant_id=tenant_id, url=data["url"]).first()
    if existing:
        raise HTTPException(400, "Source already in your feed")
    source_type = SourceType.rss if data.get("type", "rss") == "rss" else SourceType.scrape
    source = Source(
        tenant_id=tenant_id,
        name=data["name"],
        url=data["url"],
        type=source_type,
        is_active=True,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.post("/recommend")
def recommend_sources(tenant_id: int, db: Session = Depends(get_db)):
    from app.models import Tenant
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if not tenant.topic_profile:
        raise HTTPException(400, "tenant.topic_profile must be set for recommendations")
    catalog = db.query(CatalogSource).all()
    catalog_dicts = [
        {"id": c.id, "name": c.name, "category": c.category,
         "description": c.description}
        for c in catalog
    ]
    from app.services.ai.factory import get_ai_provider
    ids = get_ai_provider().recommend_sources(tenant.topic_profile, catalog_dicts)
    recommended = [c for c in catalog if c.id in ids]
    return {"recommended": [CatalogSourceRead.model_validate(c) for c in recommended]}


# ── Parameterised routes last ─────────────────────────────────────────────────

@router.get("/{catalog_id}", response_model=CatalogSourceRead)
def get_catalog_source(catalog_id: int, db: Session = Depends(get_db)):
    cs = db.get(CatalogSource, catalog_id)
    if not cs:
        raise HTTPException(404, "Catalog source not found")
    return cs


@router.put("/{catalog_id}", response_model=CatalogSourceRead)
def update_catalog_source(catalog_id: int, data: CatalogSourceUpdate,
                           db: Session = Depends(get_db)):
    cs = db.get(CatalogSource, catalog_id)
    if not cs:
        raise HTTPException(404, "Catalog source not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(cs, field, value)
    db.commit()
    db.refresh(cs)
    return cs


@router.post("/{catalog_id}/add", response_model=SourceRead)
def add_to_tenant(catalog_id: int, tenant_id: int, db: Session = Depends(get_db)):
    cs = db.get(CatalogSource, catalog_id)
    if not cs:
        raise HTTPException(404, "Catalog source not found")
    existing = (db.query(Source)
                .filter_by(tenant_id=tenant_id, catalog_source_id=catalog_id)
                .first())
    if existing:
        raise HTTPException(400, "This source is already in your feed")
    source = Source(
        tenant_id=tenant_id,
        catalog_source_id=catalog_id,
        name=cs.name,
        url=cs.url,
        type=cs.type,
        css_selector=cs.css_selector,
        is_active=True,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.get("/{catalog_id}/in-tenant/{tenant_id}")
def is_in_tenant(catalog_id: int, tenant_id: int, db: Session = Depends(get_db)):
    existing = (db.query(Source)
                .filter_by(tenant_id=tenant_id, catalog_source_id=catalog_id)
                .first())
    return {"added": existing is not None,
            "source_id": existing.id if existing else None}
