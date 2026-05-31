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


def _check_url(url: str) -> bool:
    try:
        import httpx
        with httpx.Client(timeout=6, follow_redirects=True) as c:
            r = c.head(url)
            return r.status_code < 400
    except Exception:
        return False


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
    try:
        suggestions = ai.discover_sources(tenant.topic_profile)
    except Exception as exc:
        logger.error("Source discovery failed: %s", exc)
        raise HTTPException(500, f"AI source discovery failed: {exc}")

    if not suggestions:
        return {"sources": []}

    # Validate URLs in parallel (max 8 seconds total)
    tenant_source_urls = {s.url for s in db.query(Source).filter_by(tenant_id=tenant_id).all()}
    catalog_urls = {c.url for c in db.query(CatalogSource).all()}

    with ThreadPoolExecutor(max_workers=min(len(suggestions), 10)) as pool:
        futures = {pool.submit(_check_url, s["url"]): i for i, s in enumerate(suggestions)}
        reachable: dict[int, bool] = {}
        for future in as_completed(futures, timeout=9):
            idx = futures[future]
            try:
                reachable[idx] = future.result()
            except Exception:
                reachable[idx] = False

    result = []
    for i, s in enumerate(suggestions):
        result.append({
            **s,
            "reachable": reachable.get(i, False),
            "already_in_feed": s["url"] in tenant_source_urls,
            "in_catalog": s["url"] in catalog_urls,
        })

    logger.info("Source discovery returned %d suggestions for '%s'", len(result), tenant.name)
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
