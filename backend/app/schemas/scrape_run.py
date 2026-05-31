from typing import Optional
from pydantic import BaseModel, ConfigDict
import datetime
from app.models.scrape_run import RunStatus


class ScrapeRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    source_id: Optional[int] = None
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    articles_found: int
    articles_new: int
    status: RunStatus
    error_message: Optional[str] = None


class ScrapeRunListResponse(BaseModel):
    items: list[ScrapeRunRead]
    total: int
    page: int
    size: int
