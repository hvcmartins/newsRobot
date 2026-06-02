import datetime
from sqlalchemy import (Column, Integer, String, Text, Boolean, DateTime,
                        Float, ForeignKey, UniqueConstraint)
from sqlalchemy.orm import relationship
from app.database import Base


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "url", name="uq_article_tenant_url"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    translated_title = Column(String(500), nullable=True)
    excerpt = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    url = Column(String(500), nullable=False)
    published_at = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, default=datetime.datetime.utcnow)
    image_url = Column(String(500), nullable=True)
    category = Column(String(100), nullable=True)
    relevance_score = Column(Float, default=0.0)
    relevance_reason = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    ai_enriched = Column(Boolean, default=False, nullable=False)
    duplicate_of_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    # Queue / archive lifecycle
    archived_at = Column(DateTime, nullable=True)   # null = in queue, set = archived
    digest_id = Column(Integer, ForeignKey("sent_digests.id", ondelete="SET NULL"),
                       nullable=True)

    tenant = relationship("Tenant", back_populates="articles")
    source = relationship("Source", back_populates="articles")
    duplicate_of = relationship("Article", remote_side="Article.id",
                                foreign_keys="[Article.duplicate_of_id]")
    digest = relationship("SentDigest", back_populates="articles",
                          foreign_keys="[Article.digest_id]")
