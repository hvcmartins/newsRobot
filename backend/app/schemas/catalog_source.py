from typing import Optional
from pydantic import BaseModel
from app.models.catalog_source import CatalogSourceType
from .base import ORMBase, UTCDatetime


class CatalogSourceBase(BaseModel):
    name: str
    url: str
    type: CatalogSourceType = CatalogSourceType.rss
    css_selector: Optional[str] = None
    category: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    language: str = "en"
    country: Optional[str] = None
    is_verified: bool = True


class CatalogSourceCreate(CatalogSourceBase):
    pass


class CatalogSourceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_verified: Optional[bool] = None


class CatalogSourceRead(CatalogSourceBase, ORMBase):
    id: int
    added_at: UTCDatetime
    updated_at: UTCDatetime
