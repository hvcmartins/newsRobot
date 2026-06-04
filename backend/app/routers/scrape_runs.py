import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ScrapeRun
from app.schemas.scrape_run import ScrapeRunRead, ScrapeRunListResponse

router = APIRouter()


@router.get("/status")
def scrape_status(tenant_id: int):
    """Return current in-progress scrape state for this tenant."""
    from app.services.scraper.runner import get_scrape_status
    return get_scrape_status(tenant_id)


@router.get("/", response_model=ScrapeRunListResponse)
def list_runs(
    tenant_id: int,
    source_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(ScrapeRun).filter(ScrapeRun.tenant_id == tenant_id)
    if source_id:
        q = q.filter(ScrapeRun.source_id == source_id)
    total = q.count()
    items = (q.order_by(ScrapeRun.started_at.desc())
             .offset((page - 1) * size)
             .limit(size)
             .all())
    return ScrapeRunListResponse(items=items, total=total, page=page, size=size)


@router.get("/{run_id}", response_model=ScrapeRunRead)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(ScrapeRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


def _do_full_scrape(tenant_id: int):
    from app.database import SessionLocal
    from app.services.scraper.runner import run_all_sources
    db = SessionLocal()
    try:
        run_all_sources(tenant_id, db)
    finally:
        db.close()


def _do_source_scrape(source_id: int):
    from app.database import SessionLocal
    from app.services.scraper.runner import run_source
    db = SessionLocal()
    try:
        run_source(source_id, db)
    finally:
        db.close()


@router.post("/trigger")
def trigger_full_scrape(tenant_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(_do_full_scrape, tenant_id)
    return {"status": "triggered", "tenant_id": tenant_id}


@router.post("/trigger/{source_id}")
def trigger_source_scrape(source_id: int, background_tasks: BackgroundTasks,
                           db: Session = Depends(get_db)):
    source = db.get(__import__("app.models", fromlist=["Source"]).Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    background_tasks.add_task(_do_source_scrape, source_id)
    return {"status": "triggered", "source_id": source_id}
