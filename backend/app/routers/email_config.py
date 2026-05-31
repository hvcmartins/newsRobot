from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EmailConfig
from app.schemas.email_config import EmailConfigCreate, EmailConfigRead, EmailConfigUpdate

router = APIRouter()


def _get_or_404(tenant_id: int, db: Session) -> EmailConfig:
    cfg = db.query(EmailConfig).filter_by(tenant_id=tenant_id).first()
    if not cfg:
        raise HTTPException(404, "Email config not found for this tenant")
    return cfg


@router.get("/{tenant_id}", response_model=EmailConfigRead)
def get_config(tenant_id: int, db: Session = Depends(get_db)):
    return _get_or_404(tenant_id, db)


@router.post("/", response_model=EmailConfigRead, status_code=201)
def create_config(data: EmailConfigCreate, db: Session = Depends(get_db)):
    if db.query(EmailConfig).filter_by(tenant_id=data.tenant_id).first():
        raise HTTPException(400, "Email config already exists for this tenant")
    cfg = EmailConfig(**data.model_dump())
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    from app.services.scheduler import refresh_tenant_job
    refresh_tenant_job(cfg.tenant_id)
    return cfg


@router.api_route("/{tenant_id}", methods=["PUT", "PATCH"], response_model=EmailConfigRead)
def update_config(tenant_id: int, data: EmailConfigUpdate,
                  db: Session = Depends(get_db)):
    cfg = _get_or_404(tenant_id, db)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(cfg, field, value)
    db.commit()
    db.refresh(cfg)
    from app.services.scheduler import refresh_tenant_job
    refresh_tenant_job(tenant_id)
    return cfg


@router.post("/{tenant_id}/test")
def test_send(tenant_id: int, db: Session = Depends(get_db)):
    cfg = _get_or_404(tenant_id, db)
    from app.services.email.builder import build_email_context
    from app.services.email.sender import render_email, send_email_raw
    context = build_email_context(tenant_id, None, "daily", db)
    if not context:
        raise HTTPException(400, "No articles available to preview")
    html, text = render_email(context)
    try:
        send_email_raw(cfg, f"[TEST] {context['subject']}", html, text,
                       [cfg.from_email])
        return {"sent_to": cfg.from_email}
    except Exception as exc:
        raise HTTPException(500, f"Send failed: {exc}")


@router.get("/{tenant_id}/preview", response_class=HTMLResponse)
def preview_email(tenant_id: int, db: Session = Depends(get_db)):
    from app.services.email.builder import build_email_context
    from app.services.email.sender import render_email
    context = build_email_context(tenant_id, None, "daily", db)
    if not context:
        return HTMLResponse("<p>No articles available to preview.</p>")
    html, _ = render_email(context)
    return HTMLResponse(html)
