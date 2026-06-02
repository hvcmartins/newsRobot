import datetime
import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from app.database import Base


class DigestType(str, enum.Enum):
    regular = "regular"
    monthly = "monthly"
    yearly = "yearly"


class SentDigest(Base):
    __tablename__ = "sent_digests"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    subject = Column(String(500), nullable=True)
    article_count = Column(Integer, default=0, nullable=False)
    digest_type = Column(Enum(DigestType), default=DigestType.regular, nullable=False)

    articles = relationship("Article", back_populates="digest",
                            foreign_keys="[Article.digest_id]")
