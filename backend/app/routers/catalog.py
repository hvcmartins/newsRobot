import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models import CatalogSource, Source
from app.schemas.catalog_source import (CatalogSourceCreate, CatalogSourceRead,
                                         CatalogSourceUpdate)
from app.schemas.source import SourceRead

router = APIRouter()


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
        with httpx.Client(timeout=7, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (compatible; NewsRobot/1.0)"}) as c:
            try:
                r = c.head(url)
                if r.status_code < 400:
                    return True, None
            except Exception:
                pass

            # Original URL failed — try to find a real feed on the same domain
            base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            for path in _FEED_PATHS:
                candidate = base + path
                if candidate == url:
                    continue
                try:
                    r = c.head(candidate)
                    if _is_feed_response(r):
                        return True, candidate
                except Exception:
                    continue
    except Exception:
        pass
    return False, None


@router.post("/discover")
def discover_sources(tenant_id: int, db: Session = Depends(get_db)):
    """Ask the AI to suggest new sources matching the tenant's topic profile.
    Validates each suggested URL in parallel and returns reachability status."""
    from app.models import Tenant
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if not tenant.topic_profile:
        raise HTTPException(400, "Set an AI Topic Profile first before discovering sources.")

    from app.services.ai.factory import get_ai_provider
    from app.services.ai.null import NullProvider
    ai = get_ai_provider()
    if isinstance(ai, NullProvider):
        raise HTTPException(400, "Configure an AI provider in AI Settings to use source discovery.")

    logger.info("Source discovery requested for '%s'", tenant.name)

    ai_error: Exception | None = None
    try:
        suggestions = ai.discover_sources(tenant.topic_profile)
    except Exception as exc:
        logger.error("AI source discovery failed: %s", exc)
        ai_error = exc
        suggestions = []

    # Augment with real internet search (non-blocking — failure is acceptable)
    try:
        from app.services.feed_search import web_search_feeds
        web_feeds = web_search_feeds(tenant.topic_profile)
        ai_urls = {s["url"] for s in suggestions}
        new_from_web = [f for f in web_feeds if f["url"] not in ai_urls]
        if new_from_web:
            logger.info("Web search added %d sources for '%s'", len(new_from_web), tenant.name)
            suggestions = suggestions + new_from_web
    except Exception as exc:
        logger.warning("Web feed search failed (non-critical): %s", exc)

    if not suggestions:
        if ai_error:
            raise HTTPException(500, f"AI source discovery failed: {ai_error}")
        return {"sources": []}

    # Validate URLs in parallel (max 8 seconds total)
    tenant_source_urls = {s.url for s in db.query(Source).filter_by(tenant_id=tenant_id).all()}
    catalog_urls = {c.url for c in db.query(CatalogSource).all()}

    with ThreadPoolExecutor(max_workers=min(len(suggestions), 10)) as pool:
        futures = {pool.submit(_check_url, s["url"]): i for i, s in enumerate(suggestions)}
        check_results: dict[int, tuple[bool, str | None]] = {}
        for future in as_completed(futures, timeout=12):
            idx = futures[future]
            try:
                check_results[idx] = future.result()
            except Exception:
                check_results[idx] = (False, None)

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

    # Reachable sources first, then offline — within each group keep original order
    result.sort(key=lambda s: (0 if s["reachable"] else 1))

    logger.info("Source discovery: %d reachable / %d total for '%s'",
                sum(1 for s in result if s["reachable"]), len(result), tenant.name)
    return {"sources": result}


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
