import datetime
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import app.compat  # noqa: F401 — must run before feedparser is imported
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

_BUILD_TIME = datetime.datetime.utcnow().isoformat()

from app.config import settings
from app.database import create_tables
from app.routers import tenants, sources, articles, email_config, scrape_runs, catalog, ai_config, ai_usage
from app.routers import logs as logs_router

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Attach the in-memory buffer handler so UI log page receives app events
from app.services.log_buffer import LogBufferHandler as _LogBufferHandler
logging.getLogger().addHandler(_LogBufferHandler())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    from app.services.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="NewsRobot API", version="1.0.0", lifespan=lifespan, redirect_slashes=False)

origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok", "started_at": _BUILD_TIME}

app.include_router(tenants.router,      prefix="/api/tenants",      tags=["tenants"])
app.include_router(sources.router,      prefix="/api/sources",      tags=["sources"])
app.include_router(articles.router,     prefix="/api/articles",     tags=["articles"])
app.include_router(email_config.router, prefix="/api/email-config", tags=["email"])
app.include_router(scrape_runs.router,  prefix="/api/scrape-runs",  tags=["scrape-runs"])
app.include_router(catalog.router,      prefix="/api/catalog",      tags=["catalog"])
app.include_router(ai_config.router,    prefix="/api/ai-config",    tags=["ai"])
app.include_router(ai_usage.router,     prefix="/api/ai",           tags=["ai"])
app.include_router(logs_router.router,  prefix="/api/logs",         tags=["logs"])

# Serve built React frontend — check both Docker layout and local dev layout
_static_dir = next(
    (p for p in [
        Path(__file__).parent.parent / "static",         # Docker: /app/static
        Path(__file__).parent.parent.parent / "static",  # local dev
    ] if p.exists()),
    None,
)
if _static_dir:
    # Serve hashed asset bundles under /assets/ directly
    _assets = _static_dir / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    # Serve other static root files (favicon, etc.)
    from fastapi.responses import FileResponse, Response

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        f = _static_dir / "favicon.svg"
        return FileResponse(str(f)) if f.exists() else Response(status_code=404)

    # SPA catch-all — every non-API path gets index.html so React Router works
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = _static_dir / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return Response(status_code=404)
