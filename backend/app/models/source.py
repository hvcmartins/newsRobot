import datetime
import enum
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.database import Base


class SourceType(str, enum.Enum):
    rss = "rss"
    scrape = "scrape"


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    catalog_source_id = Column(Integer, ForeignKey("catalog_sources.id"), nullable=True)
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    type = Column(Enum(SourceType), nullable=False, default=SourceType.rss)
    css_selector = Column(String(500), nullable=True)
    keywords = Column(Text, nullable=True, default="[]")
    is_active = Column(Boolean, default=True, nullable=False)
    last_scraped_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)

    tenant = relationship("Tenant", back_populates="sources")
    catalog_source = relationship("CatalogSource", back_populates="sources")
    articles = relationship("Article", back_populates="source")
    scrape_runs = relationship("ScrapeRun", back_populates="source")
