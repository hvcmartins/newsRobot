import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai_config import AIConfig
from app.schemas.ai_config import AIConfigRead, AIConfigUpdate
from app.services.ai.factory import reset_provider

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_or_create(db: Session) -> AIConfig:
    cfg = db.query(AIConfig).first()
    if not cfg:
        cfg = AIConfig(id=1)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _to_read(cfg: AIConfig) -> AIConfigRead:
    return AIConfigRead(
        is_enabled=cfg.is_enabled,
        provider=cfg.provider,
        api_key_set=bool(cfg.api_key),
        model=cfg.model,
        base_url=cfg.base_url,
        local_model_id=cfg.local_model_id,
    )


@router.get("", response_model=AIConfigRead)
def get_ai_config(db: Session = Depends(get_db)):
    return _to_read(_get_or_create(db))


@router.api_route("", methods=["PUT", "PATCH"], response_model=AIConfigRead)
def update_ai_config(payload: AIConfigUpdate, db: Session = Depends(get_db)):
    cfg = _get_or_create(db)
    cfg.is_enabled = payload.is_enabled
    cfg.provider = payload.provider
    if payload.api_key is not None:
        cfg.api_key = payload.api_key.strip() or None
    cfg.model = payload.model.strip() if payload.model else None
    cfg.base_url = payload.base_url.strip() if payload.base_url else None
    if payload.local_model_id is not None:
        cfg.local_model_id = payload.local_model_id or None
    db.commit()
    db.refresh(cfg)
    reset_provider()
    return _to_read(cfg)


@router.post("/test")
def test_ai_config(db: Session = Depends(get_db)):
    from app.services.ai.factory import get_ai_provider
    try:
        provider = get_ai_provider(db)
        result = provider.summarize(
            "Artificial Intelligence Transforms News Industry",
            "AI tools are being used in newsrooms to automate tasks and surface relevant stories.",
        )
        return {"ok": True, "response": result}
    except Exception as exc:
        logger.exception("AI test failed")
        return {"ok": False, "error": str(exc)}


# ── Local model endpoints ─────────────────────────────────────────────────────

@router.get("/local-models")
def list_local_models():
    from app.services.ai.local_models import get_all_statuses
    return get_all_statuses()


@router.get("/local-models/{model_id}")
def get_local_model(model_id: str):
    from app.services.ai.local_models import get_status
    s = get_status(model_id)
    if s.get("status") == "unknown":
        raise HTTPException(status_code=404, detail="Unknown model")
    return s


@router.post("/local-models/{model_id}/download")
def download_local_model(model_id: str):
    from app.services.ai.local_models import start_download, get_status, CATALOG
    if not any(m["id"] == model_id for m in CATALOG):
        raise HTTPException(status_code=404, detail="Unknown model")
    status = get_status(model_id)
    if status.get("status") == "ready":
        return {"message": "Already downloaded"}
    start_download(model_id)
    return {"message": "Download started"}


@router.delete("/local-models/{model_id}")
def delete_local_model(model_id: str):
    from app.services.ai.local_models import delete_model, CATALOG
    if not any(m["id"] == model_id for m in CATALOG):
        raise HTTPException(status_code=404, detail="Unknown model")
    delete_model(model_id)
    reset_provider()
    return {"message": "Deleted"}
