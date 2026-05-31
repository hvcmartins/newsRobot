from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()


@router.get("")
def list_logs(since: int = 0, source: Optional[str] = None):
    from app.services.log_buffer import get_logs
    return get_logs(since, source)


@router.delete("")
def clear_logs():
    from app.services.log_buffer import clear_logs
    clear_logs()
    return {"ok": True}
