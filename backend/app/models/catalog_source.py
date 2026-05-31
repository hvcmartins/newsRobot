import datetime
import enum
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from app.database import Base


class CatalogSourceType(str, enum.Enum):
    rss = "rss"
    scrape = "scrape"


class CatalogSource(Base):
    __tablename__ = "catalog_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False, unique=True)
    type = Column(Enum(CatalogSourceType), nullable=False, default=CatalogSourceType.rss)
    css_selector = Column(String(500), nullable=True)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)
    language = Column(String(10), nullable=False, default="en")
    country = Column(String(10), nullable=True)
    is_verified = Column(Boolean, default=True, nullable=False)

    added_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)

    sources = relationship("Source", back_populates="catalog_source")
