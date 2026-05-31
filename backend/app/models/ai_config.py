import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class AIConfig(Base):
    __tablename__ = "ai_config"

    id = Column(Integer, primary_key=True)  # singleton, always id=1
    is_enabled = Column(Boolean, default=False, nullable=False)
    provider = Column(String(50), default="none", nullable=False)
    api_key = Column(String(500), nullable=True)
    model = Column(String(100), nullable=True)
    base_url = Column(String(500), nullable=True)        # ollama custom URL
    local_model_id = Column(String(100), nullable=True)  # llamacpp selected model
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)
