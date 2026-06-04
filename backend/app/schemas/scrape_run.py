from typing import Optional
from pydantic import BaseModel
from app.models.scrape_run import RunStatus
from .base import ORMBase, UTCDatetime


class ScrapeRunRead(ORMBase):
    id: int
    tenant_id: int
    source_id: Optional[int] = None
    started_at: UTCDatetime
    completed_at: Optional[UTCDatetime] = None
    articles_found: int
    articles_new: int
    status: RunStatus
    error_message: Optional[str] = None


class ScrapeRunListResponse(BaseModel):
    items: list[ScrapeRunRead]
    total: int
    page: int
    size: int
