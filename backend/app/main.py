import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import create_tables
from app.routers import tenants, sources, articles, email_config, scrape_runs, catalog

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    from app.services.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="NewsRobot API", version="1.0.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tenants.router,      prefix="/api/tenants",      tags=["tenants"])
app.include_router(sources.router,      prefix="/api/sources",      tags=["sources"])
app.include_router(articles.router,     prefix="/api/articles",     tags=["articles"])
app.include_router(email_config.router, prefix="/api/email-config", tags=["email"])
app.include_router(scrape_runs.router,  prefix="/api/scrape-runs",  tags=["scrape-runs"])
app.include_router(catalog.router,      prefix="/api/catalog",      tags=["catalog"])

# Serve built React frontend (production Docker image)
_static_dir = Path(__file__).parent.parent.parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
