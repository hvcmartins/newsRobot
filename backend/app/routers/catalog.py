from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CatalogSource, Source
from app.schemas.catalog_source import (CatalogSourceCreate, CatalogSourceRead,
                                         CatalogSourceUpdate)
from app.schemas.source import SourceRead

router = APIRouter()


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


@router.get("/{catalog_id}", response_model=CatalogSourceRead)
def get_catalog_source(catalog_id: int, db: Session = Depends(get_db)):
    cs = db.get(CatalogSource, catalog_id)
    if not cs:
        raise HTTPException(404, "Catalog source not found")
    return cs


@router.post("/", response_model=CatalogSourceRead, status_code=201)
def create_catalog_source(data: CatalogSourceCreate, db: Session = Depends(get_db)):
    if db.query(CatalogSource).filter_by(url=data.url).first():
        raise HTTPException(400, "URL already exists in catalog")
    cs = CatalogSource(**data.model_dump())
    db.add(cs)
    db.commit()
    db.refresh(cs)
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
