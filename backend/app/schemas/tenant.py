from typing import Optional
from pydantic import BaseModel, field_validator
import re
from .base import ORMBase, UTCDatetime


class TenantBase(BaseModel):
    name: str
    slug: str
    logo_url: Optional[str] = None
    primary_color: str = "#0066cc"
    global_keywords: Optional[str] = "[]"
    schedule_cron: str = "0 * * * *"
    topic_profile: Optional[str] = None
    ai_categories: Optional[str] = None
    max_article_age_days: Optional[int] = None
    accepted_languages: Optional[str] = None    # JSON list e.g. '["en","pt","fr"]'
    translation_language: Optional[str] = None  # e.g. "en"


class TenantCreate(TenantBase):
    @field_validator('slug')
    @classmethod
    def slug_must_be_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('slug cannot be empty')
        if not re.match(r'^[a-z0-9][a-z0-9-]*$', v):
            raise ValueError('slug must contain only lowercase letters, numbers, and hyphens')
        return v


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    global_keywords: Optional[str] = None
    schedule_cron: Optional[str] = None
    topic_profile: Optional[str] = None
    ai_categories: Optional[str] = None
    max_article_age_days: Optional[int] = None
    accepted_languages: Optional[str] = None
    translation_language: Optional[str] = None


class TenantRead(TenantBase, ORMBase):
    id: int
    scrape_paused: bool = False
    created_at: UTCDatetime
    updated_at: UTCDatetime
