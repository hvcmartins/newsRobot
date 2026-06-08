import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EmailConfig
from app.schemas.email_config import EmailConfigCreate, EmailConfigRead, EmailConfigUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


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
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == 'smtp_password' and value == '':
            continue  # empty string = keep existing password (UI never receives the real value)
        setattr(cfg, field, value)
    db.commit()
    db.refresh(cfg)
    from app.services.scheduler import refresh_tenant_job
    refresh_tenant_job(tenant_id)
    return cfg


@router.get("/{tenant_id}/diagnose")
def diagnose(tenant_id: int, db: Session = Depends(get_db)):
    """Return SMTP config details (no password) to help debug send failures."""
    cfg = _get_or_404(tenant_id, db)
    import json
    return {
        "smtp_host": cfg.smtp_host,
        "smtp_port": cfg.smtp_port,
        "smtp_user": cfg.smtp_user,
        "smtp_password_set": bool(cfg.smtp_password),
        "from_email": cfg.from_email,
        "from_name": cfg.from_name,
        "recipients": json.loads(cfg.recipients_json or "[]"),
        "is_active": cfg.is_active,
        "test_will_send_to": cfg.from_email,
    }


@router.post("/{tenant_id}/test")
def test_send(tenant_id: int, db: Session = Depends(get_db)):
    cfg = _get_or_404(tenant_id, db)
    from app.services.email.builder import build_email_context
    from app.services.email.sender import render_email, send_email_raw

    context = build_email_context(tenant_id, None, "immediate", db, preview=True)
    if context:
        html, text = render_email(context)
        subject = f"[TEST] {context['subject']}"
    else:
        subject = "[TEST] NewsRobot email configuration"
        html = (
            "<div style='font-family:sans-serif;padding:32px;max-width:600px'>"
            "<h2 style='color:#333'>Email configuration is working ✓</h2>"
            "<p style='color:#666'>Your SMTP settings are correct. "
            "Articles will appear here once your sources have been scraped.</p>"
            "</div>"
        )
        text = "Email configuration is working. Your SMTP settings are correct."

    import json as _json
    recipients = _json.loads(cfg.recipients_json or "[]") or [cfg.from_email]
    logger.info("Test email: host=%s port=%s user=%s has_password=%s from=%s to=%s",
                cfg.smtp_host, cfg.smtp_port, cfg.smtp_user,
                bool(cfg.smtp_password), cfg.from_email, recipients)
    try:
        send_email_raw(cfg, subject, html, text, recipients)
        logger.info("Test email sent successfully to %s", recipients)
        return {"sent_to": recipients, "subject": subject,
                "smtp_host": cfg.smtp_host, "smtp_port": cfg.smtp_port}
    except Exception as exc:
        logger.error("Test email failed: %s", exc, exc_info=True)
        raise HTTPException(500, f"Send failed: {exc}")


@router.post("/{tenant_id}/ping")
def ping_smtp(tenant_id: int, db: Session = Depends(get_db)):
    """Test SMTP connectivity and authentication without sending any email."""
    cfg = _get_or_404(tenant_id, db)
    from app.services.email.sender import ping_smtp as _ping
    try:
        status = _ping(cfg)
        return {"ok": True, "host": cfg.smtp_host, "port": cfg.smtp_port, "status": status}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.post("/{tenant_id}/send-now")
def send_now(tenant_id: int, db: Session = Depends(get_db)):
    """Manually trigger a digest send for all pending articles, regardless of schedule."""
    from app.services.email.sender import send_digest_if_configured
    _get_or_404(tenant_id, db)
    try:
        sent = send_digest_if_configured(tenant_id, None, "immediate", db)
        if not sent:
            raise HTTPException(400, "No pending articles or email config inactive")
        return {"sent": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Send failed: {exc}")


@router.get("/{tenant_id}/preview", response_class=HTMLResponse)
def preview_email(tenant_id: int, db: Session = Depends(get_db)):
    from app.services.email.builder import build_email_context
    from app.services.email.sender import render_email
    context = build_email_context(tenant_id, None, "preview", db, preview=True)
    if not context:
        return HTMLResponse("<p style='font-family:sans-serif;padding:32px;color:#666'>No articles yet — trigger a scrape from the News Feed page to populate your digest.</p>")
    html, _ = render_email(context)
    return HTMLResponse(html)
