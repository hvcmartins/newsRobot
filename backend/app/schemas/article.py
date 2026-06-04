from typing import Optional
from pydantic import BaseModel
from .base import ORMBase, UTCDatetime


class ArticleSourceRead(ORMBase):
    id: int
    name: str


class ArticleRead(ORMBase):
    id: int
    tenant_id: int
    source_id: int
    source: ArticleSourceRead
    title: str
    translated_title: Optional[str] = None
    excerpt: Optional[str] = None
    summary: Optional[str] = None
    url: str
    published_at: Optional[UTCDatetime] = None
    scraped_at: UTCDatetime
    image_url: Optional[str] = None
    category: Optional[str] = None
    relevance_score: float
    relevance_reason: Optional[str] = None
    is_read: bool
    ai_enriched: bool
    duplicate_of_id: Optional[int] = None


class ArticleListResponse(BaseModel):
    items: list[ArticleRead]
    total: int
    page: int
    size: int
    pages: int
