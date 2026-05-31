from typing import Optional
from pydantic import BaseModel, ConfigDict
import datetime


class ArticleSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class ArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    source_id: int
    source: ArticleSourceRead
    title: str
    excerpt: Optional[str] = None
    summary: Optional[str] = None
    url: str
    published_at: Optional[datetime.datetime] = None
    scraped_at: datetime.datetime
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
