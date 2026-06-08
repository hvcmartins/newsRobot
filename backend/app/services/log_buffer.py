"""
In-memory circular log buffer.

A custom logging.Handler appends records here; the /api/logs endpoint
reads from it.  The buffer is deliberately small (1000 entries) so it
never grows unbounded.
"""
import collections
import datetime
import logging
import threading

_MAX = 1000
_buffer: collections.deque = collections.deque(maxlen=_MAX)
_counter = 0
_lock = threading.Lock()

# Logger names whose records are forwarded to the UI
_APP_PREFIXES = ("app.",)

# Source classification by logger name fragments
_AI_NAMES = ("ai", "llama", "claude", "openai", "ollama", "enrichment")
_SCRAPER_NAMES = ("scraper", "rss", "web_scraper")
_SCHEDULER_NAMES = ("scheduler",)
_EMAIL_NAMES = ("email", "sender", "builder")
_QUEUE_NAMES = ("queue",)


def _classify(name: str) -> str:
    lower = name.lower()
    if any(f in lower for f in _QUEUE_NAMES):
        return "queue"
    if any(f in lower for f in _AI_NAMES):
        return "ai"
    if any(f in lower for f in _SCRAPER_NAMES):
        return "scraper"
    if any(f in lower for f in _SCHEDULER_NAMES):
        return "scheduler"
    if any(f in lower for f in _EMAIL_NAMES):
        return "email"
    return "general"


def get_logs(since: int = 0, source: str | None = None) -> list[dict]:
    with _lock:
        entries = list(_buffer)
    if since:
        entries = [e for e in entries if e["id"] > since]
    if source and source != "all":
        entries = [e for e in entries if e["source"] == source]
    return entries


def clear_logs() -> None:
    global _counter
    with _lock:
        _buffer.clear()
        _counter = 0


class LogBufferHandler(logging.Handler):
    """Captures log records from app.* loggers into the in-memory buffer."""

    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        if not any(record.name.startswith(p) for p in _APP_PREFIXES):
            return
        if record.levelno < logging.INFO:
            return
        global _counter
        try:
            msg = self.format(record)
            with _lock:
                _counter += 1
                _buffer.append({
                    "id": _counter,
                    "ts": datetime.datetime.utcnow().strftime("%H:%M:%S"),
                    "level": record.levelname,
                    "source": _classify(record.name),
                    "message": msg,
                })
        except Exception:
            pass
