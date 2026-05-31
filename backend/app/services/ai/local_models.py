import threading
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

MODELS_DIR = Path("/data/models")

CATALOG = [
    {
        "id": "llama-3.2-1b",
        "name": "Llama 3.2 1B",
        "tag": "Lite",
        "description": "Very fast, ~1.5 GB RAM. Good for weak hardware.",
        "url": "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "filename": "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "size_gb": 0.8,
        "ram_gb": 1.5,
    },
    {
        "id": "llama-3.2-3b",
        "name": "Llama 3.2 3B",
        "tag": "Recommended",
        "description": "Good quality and speed. ~3 GB RAM.",
        "url": "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "size_gb": 2.0,
        "ram_gb": 3.0,
    },
    {
        "id": "phi-3.5-mini",
        "name": "Phi-3.5 Mini",
        "tag": "Efficient",
        "description": "Microsoft's compact model. ~3 GB RAM.",
        "url": "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf",
        "filename": "Phi-3.5-mini-instruct-Q4_K_M.gguf",
        "size_gb": 2.2,
        "ram_gb": 3.0,
    },
    {
        "id": "llama-3.1-8b",
        "name": "Llama 3.1 8B",
        "tag": "High Quality",
        "description": "Best results. Needs 6 GB+ RAM.",
        "url": "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "size_gb": 4.7,
        "ram_gb": 6.0,
    },
]

# In-memory download progress {model_id: {"status": ..., "progress": int, "error": str|None}}
_progress: dict[str, dict] = {}


def model_path(model_id: str) -> Path | None:
    entry = _find(model_id)
    return (MODELS_DIR / entry["filename"]) if entry else None


def get_all_statuses() -> list[dict]:
    result = []
    for entry in CATALOG:
        result.append({**entry, **_status(entry["id"])})
    return result


def get_status(model_id: str) -> dict:
    entry = _find(model_id)
    if not entry:
        return {"status": "unknown"}
    return {**entry, **_status(model_id)}


def start_download(model_id: str) -> None:
    entry = _find(model_id)
    if not entry:
        raise ValueError(f"Unknown model id: {model_id}")
    if _progress.get(model_id, {}).get("status") == "downloading":
        return  # already in flight
    _progress[model_id] = {"status": "downloading", "progress": 0, "error": None}
    t = threading.Thread(target=_download, args=(model_id, entry), daemon=True)
    t.start()


def delete_model(model_id: str) -> None:
    entry = _find(model_id)
    if not entry:
        raise ValueError(f"Unknown model id: {model_id}")
    p = MODELS_DIR / entry["filename"]
    if p.exists():
        p.unlink()
    _progress.pop(model_id, None)


# ── internals ────────────────────────────────────────────────────────────────

def _find(model_id: str) -> dict | None:
    return next((m for m in CATALOG if m["id"] == model_id), None)


def _status(model_id: str) -> dict:
    entry = _find(model_id)
    if not entry:
        return {"status": "unknown", "progress": 0, "error": None}
    p = MODELS_DIR / entry["filename"]
    if p.exists() and p.stat().st_size > 1_000_000:
        return {"status": "ready", "progress": 100, "error": None}
    prog = _progress.get(model_id)
    if prog:
        return prog
    return {"status": "not_downloaded", "progress": 0, "error": None}


def _download(model_id: str, entry: dict) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MODELS_DIR / entry["filename"]
    tmp = dest.with_suffix(".tmp")
    try:
        logger.info("Downloading %s from %s", model_id, entry["url"])
        with httpx.stream("GET", entry["url"], follow_redirects=True,
                          timeout=httpx.Timeout(None)) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65_536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        _progress[model_id]["progress"] = min(99, int(downloaded / total * 100))
        tmp.rename(dest)
        _progress[model_id] = {"status": "ready", "progress": 100, "error": None}
        logger.info("Download complete: %s", dest)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        _progress[model_id] = {"status": "error", "progress": 0, "error": str(exc)}
        logger.error("Download failed for %s: %s", model_id, exc)
