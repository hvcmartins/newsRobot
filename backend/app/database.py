from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,          # wait up to 30s for SQLite write lock
    },
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_timeout=60,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate():
    """Add columns that were introduced after initial schema creation."""
    # WAL mode drastically reduces write contention — set once, persists in the DB file
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))
    _add_column_if_missing("ai_config", "local_model_id", "VARCHAR(100)")
    _add_column_if_missing("ai_config", "cpu_limit_percent", "INTEGER DEFAULT 80")
    _add_column_if_missing("ai_config", "n_gpu_layers", "INTEGER DEFAULT -1")
    _add_column_if_missing("ai_config", "serper_api_key", "VARCHAR(500)")
    _add_column_if_missing("ai_config", "google_search_api_key", "VARCHAR(500)")
    _add_column_if_missing("ai_config", "google_search_cx", "VARCHAR(200)")
    _add_column_if_missing("articles", "summary", "TEXT")
    _add_column_if_missing("articles", "ai_enriched", "BOOLEAN DEFAULT 0")
    _add_column_if_missing("articles", "archived_at", "DATETIME")
    _add_column_if_missing("articles", "digest_id", "INTEGER")
    _add_column_if_missing("tenants", "topic_profile", "TEXT")
    _add_column_if_missing("tenants", "ai_categories", "TEXT")
    _add_column_if_missing("tenants", "max_article_age_days", "INTEGER")
    _add_column_if_missing("tenants", "accepted_languages", "TEXT")
    _add_column_if_missing("tenants", "translation_language", "VARCHAR(10)")
    _add_column_if_missing("email_configs", "lookback_hours", "INTEGER DEFAULT 24")
    _add_column_if_missing("email_configs", "schedule_overrides", "TEXT")
    _add_column_if_missing("email_configs", "monthly_digest_enabled", "BOOLEAN DEFAULT 0")
    _add_column_if_missing("email_configs", "monthly_digest_day", "INTEGER DEFAULT 1")
    _add_column_if_missing("email_configs", "monthly_digest_time", "VARCHAR(5) DEFAULT '08:00'")
    _add_column_if_missing("email_configs", "yearly_digest_enabled", "BOOLEAN DEFAULT 0")
    _add_column_if_missing("email_configs", "yearly_digest_month", "INTEGER DEFAULT 1")
    _add_column_if_missing("email_configs", "yearly_digest_day", "INTEGER DEFAULT 1")
    _add_column_if_missing("email_configs", "yearly_digest_time", "VARCHAR(5) DEFAULT '08:00'")
    _add_column_if_missing("email_configs", "send_days", "TEXT")
    _fix_empty_slugs()


def _fix_empty_slugs() -> None:
    """Auto-repair tenants that have an empty slug (creates one from the name)."""
    import re
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, name FROM tenants WHERE slug = '' OR slug IS NULL")).fetchall()
        for row in rows:
            tenant_id, name = row[0], row[1] or ""
            slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or f"tenant-{tenant_id}"
            conn.execute(text("UPDATE tenants SET slug = :slug WHERE id = :id"),
                         {"slug": slug, "id": tenant_id})
            conn.commit()


def _add_column_if_missing(table: str, column: str, col_type: str) -> None:
    with engine.connect() as conn:
        result = conn.execute(text(f"PRAGMA table_info({table})"))
        existing = {row[1] for row in result}
        if column not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            conn.commit()

