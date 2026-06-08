from typing import Optional
from pydantic import BaseModel


class AIConfigUpdate(BaseModel):
    is_enabled: bool
    provider: str
    api_key: Optional[str] = None        # None = keep existing; "" = clear
    model: Optional[str] = None
    base_url: Optional[str] = None
    local_model_id: Optional[str] = None
    cpu_limit_percent: int = 80          # llamacpp: % of CPU cores to use (25-100)
    n_gpu_layers: int = -1               # llamacpp: GPU layers to offload (-1 = all, 0 = CPU only)
    serper_api_key: Optional[str] = None
    google_search_api_key: Optional[str] = None   # legacy
    google_search_cx: Optional[str] = None        # legacy
    relevance_threshold: float = 0.3              # articles below this score are deleted (0.0–0.9)


class AIConfigRead(BaseModel):
    is_enabled: bool
    provider: str
    api_key_set: bool                    # never expose the raw key
    model: Optional[str]
    base_url: Optional[str]
    local_model_id: Optional[str]
    cpu_limit_percent: int = 80
    n_gpu_layers: int = -1
    serper_api_key_set: bool = False
    google_search_api_key_set: bool = False
    google_search_cx: Optional[str] = None
    relevance_threshold: float = 0.3
