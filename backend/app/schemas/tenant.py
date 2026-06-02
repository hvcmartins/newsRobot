from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator
import re
import datetime


class TenantBase(BaseModel):
    name: str
    slug: str
    logo_url: Optional[str] = None
    primary_color: str = "#0066cc"
    global_keywords: Optional[str] = "[]"
    schedule_cron: str = "0 * * * *"
    topic_profile: Optional[str] = None
    ai_categories: Optional[str] = None  # JSON list e.g. '["ASEAN Affairs", "EU News"]'


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


class TenantRead(TenantBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
