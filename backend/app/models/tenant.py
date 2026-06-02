import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), nullable=False, default="#0066cc")
    global_keywords = Column(Text, nullable=True, default="[]")
    schedule_cron = Column(String(100), nullable=False, default="0 * * * *")
    topic_profile = Column(Text, nullable=True)
    ai_categories = Column(Text, nullable=True)  # JSON list generated from profile

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)

    sources = relationship("Source", back_populates="tenant",
                           cascade="all, delete-orphan")
    articles = relationship("Article", back_populates="tenant",
                            cascade="all, delete-orphan")
    email_config = relationship("EmailConfig", back_populates="tenant",
                                uselist=False, cascade="all, delete-orphan")
    scrape_runs = relationship("ScrapeRun", back_populates="tenant",
                               cascade="all, delete-orphan")
