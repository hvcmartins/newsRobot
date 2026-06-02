import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Source
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate

logger = logging.getLogger(__name__)
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


@router.post("/check-all")
def check_all_sources(tenant_id: int, db: Session = Depends(get_db)):
    """HEAD-check every source URL for a tenant in parallel. Fast connectivity test."""
    import httpx

    sources = db.query(Source).filter_by(tenant_id=tenant_id).order_by(Source.name).all()
    if not sources:
        return {"results": []}

    def _check(src: Source) -> dict:
        try:
            with httpx.Client(timeout=6, follow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0 (compatible; NewsRobot/1.0)"}) as c:
                r = c.head(src.url)
                return {"id": src.id, "online": r.status_code < 400, "http_status": r.status_code}
        except Exception as exc:
            return {"id": src.id, "online": False, "error": str(exc)[:120]}

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(len(sources), 12)) as pool:
        futures = {pool.submit(_check, s): s for s in sources}
        try:
            for future in as_completed(futures, timeout=18):
                try:
                    results.append(future.result())
                except Exception as exc:
                    s = futures[future]
                    results.append({"id": s.id, "online": False, "error": str(exc)[:120]})
        except FuturesTimeout:
            logger.warning("check-all: timed out; %d/%d completed", len(results), len(futures))
            for future, s in futures.items():
                if not future.done():
                    results.append({"id": s.id, "online": False, "error": "timeout"})

    logger.info("check-all: %d/%d online for tenant %d",
                sum(1 for r in results if r.get("online")), len(results), tenant_id)
    return {"results": results}


@router.delete("/{source_id}/scraped-urls", status_code=200)
def clear_scraped_urls(source_id: int, db: Session = Depends(get_db)):
    """Delete all scraped-URL dedup entries that came from this source's articles,
    so the source can be re-scraped as if it were fresh."""
    from app.models import Article
    from app.models.scraped_url import ScrapedUrl

    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")

    urls = [
        row[0]
        for row in db.query(Article.url)
        .filter(Article.source_id == source_id, Article.url.isnot(None))
        .all()
    ]
    if urls:
        deleted = (
            db.query(ScrapedUrl)
            .filter(ScrapedUrl.tenant_id == source.tenant_id,
                    ScrapedUrl.url.in_(urls))
            .delete(synchronize_session=False)
        )
        db.commit()
    else:
        deleted = 0

    logger.info("Cleared %d scraped-url entries for source %d ('%s')",
                deleted, source_id, source.name)
    return {"cleared": deleted, "source_id": source_id}


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
