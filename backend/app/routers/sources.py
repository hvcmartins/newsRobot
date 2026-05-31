from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Source
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate

router = APIRouter()


@router.get("/", response_model=list[SourceRead])
def list_sources(tenant_id: int, db: Session = Depends(get_db)):
    return (db.query(Source)
            .filter_by(tenant_id=tenant_id)
            .order_by(Source.name)
            .all())


@router.post("/", response_model=SourceRead, status_code=201)
def create_source(data: SourceCreate, db: Session = Depends(get_db)):
    source = Source(**data.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.get("/{source_id}", response_model=SourceRead)
def get_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    return source


@router.api_route("/{source_id}", methods=["PUT", "PATCH"], response_model=SourceRead)
def update_source(source_id: int, data: SourceUpdate, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    db.delete(source)
    db.commit()


@router.post("/{source_id}/test")
def test_source(source_id: int, db: Session = Depends(get_db)):
    """Scrape the source and return up to 5 sample articles without writing to DB."""
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    try:
        from app.models.source import SourceType
        from app.services.scraper.rss_scraper import RssScraper
        from app.services.scraper.web_scraper import WebScraper
        if source.type == SourceType.rss:
            scraper = RssScraper(source.url, source.name)
        else:
            scraper = WebScraper(source.url, source.name,
                                 source.css_selector or "article")
        articles = scraper.fetch()[:5]
        return {
            "source_name": source.name,
            "articles_found": len(articles),
            "sample": [
                {
                    "title": a.title,
                    "url": a.url,
                    "excerpt": a.excerpt,
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                    "image_url": a.image_url,
                }
                for a in articles
            ],
        }
    except Exception as exc:
        raise HTTPException(400, f"Scrape test failed: {exc}")
