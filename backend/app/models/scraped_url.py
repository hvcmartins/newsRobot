import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from app.database import Base


class ScrapedUrl(Base):
    __tablename__ = "scraped_urls"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
                       nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="SET NULL"),
                       nullable=True)
    url = Column(String(500), nullable=False)
    scraped_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "url", name="uq_scraped_url_tenant"),
        Index("ix_scraped_urls_tenant_url", "tenant_id", "url"),
        Index("ix_scraped_urls_source_id", "source_id"),
    )
