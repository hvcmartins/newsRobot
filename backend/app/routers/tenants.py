from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate

router = APIRouter()


@router.get("/", response_model=list[TenantRead])
def list_tenants(db: Session = Depends(get_db)):
    return db.query(Tenant).order_by(Tenant.name).all()


@router.post("/", response_model=TenantRead, status_code=201)
def create_tenant(data: TenantCreate, db: Session = Depends(get_db)):
    if db.query(Tenant).filter_by(slug=data.slug).first():
        raise HTTPException(400, f"Slug '{data.slug}' already exists")
    tenant = Tenant(**data.model_dump())
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    from app.services.scheduler import _add_scrape_job
    _add_scrape_job(tenant.id, tenant.schedule_cron)
    return tenant


@router.get("/{slug}", response_model=TenantRead)
def get_tenant(slug: str, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter_by(slug=slug).first()
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return tenant


@router.api_route("/{slug}", methods=["PUT", "PATCH"], response_model=TenantRead)
def update_tenant(slug: str, data: TenantUpdate, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter_by(slug=slug).first()
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    from app.services.scheduler import refresh_tenant_job
    refresh_tenant_job(tenant.id)
    return tenant


@router.delete("/{slug}", status_code=204)
def delete_tenant(slug: str, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter_by(slug=slug).first()
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    tid = tenant.id
    db.delete(tenant)
    db.commit()
    from app.services.scheduler import scheduler
    for jid in (f"scrape_{tid}", f"email_{tid}"):
        if scheduler.get_job(jid):
            scheduler.remove_job(jid)


@router.post("/{slug}/suggest-keywords")
def suggest_keywords(slug: str, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter_by(slug=slug).first()
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if not tenant.topic_profile:
        raise HTTPException(400, "topic_profile is required")
    from app.services.ai.factory import get_ai_provider
    keywords = get_ai_provider().suggest_keywords(tenant.topic_profile)
    return {"keywords": keywords}
