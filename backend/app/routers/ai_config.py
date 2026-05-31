import logging
from fastapi import APIRouter, Depends
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
    )


@router.get("", response_model=AIConfigRead)
def get_ai_config(db: Session = Depends(get_db)):
    return _to_read(_get_or_create(db))


@router.put("", response_model=AIConfigRead)
def update_ai_config(payload: AIConfigUpdate, db: Session = Depends(get_db)):
    cfg = _get_or_create(db)
    cfg.is_enabled = payload.is_enabled
    cfg.provider = payload.provider
    # api_key=None means "don't touch it"; api_key="" means "clear it"
    if payload.api_key is not None:
        cfg.api_key = payload.api_key.strip() or None
    cfg.model = payload.model.strip() if payload.model else None
    cfg.base_url = payload.base_url.strip() if payload.base_url else None
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
            "AI tools are increasingly being used in newsrooms to automate routine "
            "tasks, summarize articles, and surface relevant stories for journalists.",
        )
        return {"ok": True, "response": result}
    except Exception as exc:
        logger.exception("AI test failed")
        return {"ok": False, "error": str(exc)}
