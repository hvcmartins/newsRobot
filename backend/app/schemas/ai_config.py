from typing import Optional
from pydantic import BaseModel


class AIConfigUpdate(BaseModel):
    is_enabled: bool
    provider: str
    api_key: Optional[str] = None        # None = keep existing; "" = clear
    model: Optional[str] = None
    base_url: Optional[str] = None
    local_model_id: Optional[str] = None


class AIConfigRead(BaseModel):
    is_enabled: bool
    provider: str
    api_key_set: bool                    # never expose the raw key
    model: Optional[str]
    base_url: Optional[str]
    local_model_id: Optional[str]
