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
    cpu_limit_percent = Column(Integer, default=80, nullable=False)  # llamacpp thread cap
    n_gpu_layers = Column(Integer, default=-1, nullable=False)       # llamacpp GPU layers (-1 = all)
    embedding_model = Column(String(100), nullable=True)              # e.g. nomic-embed-text / text-embedding-3-small
    serper_api_key = Column(String(500), nullable=True)              # Serper.dev (Google Search)
    google_search_api_key = Column(String(500), nullable=True)       # Google Custom Search (legacy)
    google_search_cx = Column(String(200), nullable=True)            # Custom Search Engine ID (legacy)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)
