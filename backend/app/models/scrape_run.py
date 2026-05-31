import datetime
import enum
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.database import Base


class RunStatus(str, enum.Enum):
    running = "running"
    success = "success"
    partial = "partial"
    error = "error"


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    articles_found = Column(Integer, default=0)
    articles_new = Column(Integer, default=0)
    status = Column(Enum(RunStatus), default=RunStatus.running)
    error_message = Column(Text, nullable=True)

    tenant = relationship("Tenant", back_populates="scrape_runs")
    source = relationship("Source", back_populates="scrape_runs")
