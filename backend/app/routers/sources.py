import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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


@router.post("/import-csv")
async def import_csv_sources(
    tenant_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Bulk-import sources from a CSV file with columns: Name, URL, Type.

    Type must be 'rss' or 'scrape' (case-insensitive; defaults to 'rss').
    An optional 'CSS Selector' column is used for type=scrape sources.
    Rows with duplicate URLs (already present for this tenant) are skipped.
    """
    import csv
    import io
    from app.models.source import SourceType

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # strip BOM added by Excel
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(400, "CSV file appears to be empty or has no header row")

    imported: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []

    for row_num, row in enumerate(reader, start=2):  # row 1 is the header
        norm = {k.lower().strip(): (v or "").strip() for k, v in row.items() if k}
        name = norm.get("name", "")
        url = norm.get("url", "")
        type_str = norm.get("type", "rss").lower()
        css = norm.get("css selector", "") or norm.get("css_selector", "")

        if not name or not url:
            errors.append({"row": row_num, "error": "Missing Name or URL"})
            continue
        if not url.startswith("http"):
            errors.append({"row": row_num, "name": name, "error": f"Invalid URL: {url}"})
            continue

        src_type = SourceType.scrape if "scrape" in type_str else SourceType.rss

        if db.query(Source).filter_by(tenant_id=tenant_id, url=url).first():
            skipped.append({"row": row_num, "name": name, "url": url})
            continue

        db.add(Source(
            tenant_id=tenant_id,
            name=name,
            url=url,
            type=src_type,
            css_selector=css or None,
            is_active=True,
        ))
        imported.append({"name": name, "url": url, "type": src_type.value})

    db.commit()
    logger.info("CSV import for tenant %d: %d imported, %d skipped, %d errors",
                tenant_id, len(imported), len(skipped), len(errors))
    return {
        "imported": len(imported),
        "skipped": len(skipped),
        "errors": len(errors),
        "rows": {"imported": imported, "skipped": skipped, "errors": errors},
    }


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
    from app.models import Article, ScrapedUrl
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    try:
        # Null out duplicate_of_id references that point to this source's articles
        sub = db.query(Article.id).filter(Article.source_id == source_id).subquery()
        db.query(Article).filter(Article.duplicate_of_id.in_(sub)).update(
            {Article.duplicate_of_id: None}, synchronize_session=False)
        # Remove scraped-URL dedup records for this source's articles
        urls = [r[0] for r in db.query(Article.url)
                .filter(Article.source_id == source_id, Article.url.isnot(None)).all()]
        if urls:
            db.query(ScrapedUrl).filter(
                ScrapedUrl.tenant_id == source.tenant_id,
                ScrapedUrl.url.in_(urls),
            ).delete(synchronize_session=False)
        # Delete articles, then the source
        db.query(Article).filter(Article.source_id == source_id).delete(
            synchronize_session=False)
        db.delete(source)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("delete_source %d failed: %s", source_id, exc)
        raise HTTPException(500, f"Could not delete source: {exc}")


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
                    "published_at": a.published_at.replace(tzinfo=datetime.timezone.utc).isoformat() if a.published_at else None,
                    "image_url": a.image_url,
                }
                for a in articles
            ],
        }
    except Exception as exc:
        raise HTTPException(400, f"Scrape test failed: {exc}")
