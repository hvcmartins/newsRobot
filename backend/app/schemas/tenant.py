from typing import Optional
from pydantic import BaseModel, ConfigDict
import datetime


class TenantBase(BaseModel):
    name: str
    slug: str
    logo_url: Optional[str] = None
    primary_color: str = "#0066cc"
    global_keywords: Optional[str] = "[]"
    schedule_cron: str = "0 * * * *"
    topic_profile: Optional[str] = None


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    global_keywords: Optional[str] = None
    schedule_cron: Optional[str] = None
    topic_profile: Optional[str] = None


class TenantRead(TenantBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
