from typing import Optional
from pydantic import BaseModel
from app.models.source import SourceType
from .base import ORMBase, UTCDatetime


class SourceBase(BaseModel):
    tenant_id: int
    name: str
    url: str
    type: SourceType = SourceType.rss
    css_selector: Optional[str] = None
    keywords: Optional[str] = "[]"
    is_active: bool = True
    catalog_source_id: Optional[int] = None


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    type: Optional[SourceType] = None
    css_selector: Optional[str] = None
    keywords: Optional[str] = None
    is_active: Optional[bool] = None


class SourceRead(SourceBase, ORMBase):
    id: int
    last_scraped_at: Optional[UTCDatetime] = None
    created_at: UTCDatetime
    updated_at: UTCDatetime
