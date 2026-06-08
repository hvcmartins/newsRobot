import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Source, Article
from app.models.scraped_url import ScrapedUrl

logger = logging.getLogger(__name__)
router = APIRouter()


def _row_to_dict(row: ScrapedUrl, source_map: dict, article_map: dict) -> dict:
    art = article_map.get(row.url)
    return {
        "id": row.id,
        "url": row.url,
        "source_id": row.source_id,
        "source_name": source_map.get(row.source_id) if row.source_id else None,
        "scraped_at": row.scraped_at.isoformat() if row.scraped_at else None,
        # article_id / article_archived let the UI warn that removing this
        # entry won't allow re-scraping until the article itself is deleted.
        "article_id": art["id"] if art else None,
        "article_archived": art["archived"] if art else None,
    }


@router.get("/")
def list_scraped_urls(
    tenant_id: int,
    source_id: Optional[int] = None,
    q: str = "",
    page: int = 1,
    size: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    base = db.query(ScrapedUrl).filter(ScrapedUrl.tenant_id == tenant_id)
    if source_id is not None:
        base = base.filter(ScrapedUrl.source_id == source_id)
    if q:
        base = base.filter(ScrapedUrl.url.ilike(f"%{q}%"))

    total = base.count()
    rows = (
        base.order_by(ScrapedUrl.scraped_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    # Resolve source names in one query
    source_ids = {r.source_id for r in rows if r.source_id}
    source_map: dict = {}
    if source_ids:
        for src in db.query(Source.id, Source.name).filter(Source.id.in_(source_ids)).all():
            source_map[src.id] = src.name

    # Check which URLs still have a live Article — those will still be detected
    # as duplicates even after removing the ScrapedUrl entry.
    page_urls = [r.url for r in rows]
    article_map: dict = {}
    if page_urls:
        arts = (
            db.query(Article.id, Article.url, Article.archived_at)
            .filter(Article.tenant_id == tenant_id, Article.url.in_(page_urls))
            .all()
        )
        for a in arts:
            article_map[a.url] = {"id": a.id, "archived": a.archived_at is not None}

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [_row_to_dict(r, source_map, article_map) for r in rows],
    }


class AddUrlBody(BaseModel):
    tenant_id: int
    url: str
    source_id: Optional[int] = None


@router.post("/", status_code=201)
def add_scraped_url(body: AddUrlBody, db: Session = Depends(get_db)):
    import datetime
    from sqlalchemy.exc import IntegrityError

    # Validate source belongs to tenant
    if body.source_id:
        src = db.get(Source, body.source_id)
        if not src or src.tenant_id != body.tenant_id:
            raise HTTPException(400, "Source not found for this tenant")

    row = ScrapedUrl(
        tenant_id=body.tenant_id,
        source_id=body.source_id,
        url=body.url.strip(),
        scraped_at=datetime.datetime.utcnow(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "URL already in seen list for this tenant")
    db.refresh(row)
    source_map = {}
    if row.source_id:
        src = db.get(Source, row.source_id)
        if src:
            source_map[src.id] = src.name
    logger.info("Manually added scraped URL for tenant %d: %s", body.tenant_id, body.url)
    return _row_to_dict(row, source_map)


@router.delete("/{url_id}", status_code=200)
def delete_scraped_url(
    url_id: int,
    tenant_id: int,
    delete_article: bool = False,
    db: Session = Depends(get_db),
):
    row = db.get(ScrapedUrl, url_id)
    if not row or row.tenant_id != tenant_id:
        raise HTTPException(404, "Entry not found")
    article_deleted = 0
    if delete_article:
        art = db.query(Article).filter_by(tenant_id=tenant_id, url=row.url).first()
        if art:
            db.delete(art)
            article_deleted = 1
    db.delete(row)
    db.commit()
    return {"deleted": 1, "id": url_id, "article_deleted": article_deleted}


class BulkDeleteBody(BaseModel):
    ids: list[int]
    tenant_id: int


@router.post("/bulk-delete", status_code=200)
def bulk_delete_scraped_urls(body: BulkDeleteBody, db: Session = Depends(get_db)):
    deleted = (
        db.query(ScrapedUrl)
        .filter(
            ScrapedUrl.id.in_(body.ids),
            ScrapedUrl.tenant_id == body.tenant_id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info("Bulk-deleted %d scraped URL entries for tenant %d", deleted, body.tenant_id)
    return {"deleted": deleted}


@router.delete("/", status_code=200)
def clear_scraped_urls(
    tenant_id: int,
    source_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    base = db.query(ScrapedUrl).filter(ScrapedUrl.tenant_id == tenant_id)
    if source_id is not None:
        base = base.filter(ScrapedUrl.source_id == source_id)
    deleted = base.delete(synchronize_session=False)
    db.commit()
    logger.info("Cleared %d scraped URL entries for tenant %d (source_id=%s)",
                deleted, tenant_id, source_id)
    return {"deleted": deleted}
