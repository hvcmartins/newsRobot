import datetime
import json
import logging
from collections import defaultdict
from sqlalchemy.orm import Session

from app.models import Tenant, EmailConfig, Article, EmailFrequency

logger = logging.getLogger(__name__)


def build_email_context(tenant_id: int, articles: list | None,
                         frequency: str, db: Session,
                         preview: bool = False) -> dict | None:
    tenant: Tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return None

    config: EmailConfig = (db.query(EmailConfig)
                           .filter_by(tenant_id=tenant_id)
                           .first())

    if not preview:
        if not config or not config.is_active:
            return None
        recipients = json.loads(config.recipients_json or "[]")
        if not recipients:
            return None
    else:
        recipients = json.loads(config.recipients_json or "[]") if config else []

    # all_pending_articles: every queued article — used for archiving after send
    all_pending: list | None = None

    if articles is None:
        default_hours = (config.lookback_hours if config and config.lookback_hours
                         else {"daily": 24, "weekly": 168}.get(frequency, 24))

        hours = default_hours
        if config and config.schedule_overrides:
            overrides = json.loads(config.schedule_overrides or "{}")
            weekday = datetime.datetime.utcnow().strftime("%A").lower()
            hours = int(overrides.get(weekday, default_hours))

        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)

        query = (db.query(Article)
                 .filter(Article.tenant_id == tenant_id,
                         Article.duplicate_of_id.is_(None),
                         Article.archived_at.is_(None)))
        if frequency != "immediate":
            query = query.filter(Article.scraped_at >= cutoff)

        all_pending = (query
                       .order_by(Article.relevance_score.desc(),
                                 Article.published_at.desc())
                       .limit(500)
                       .all())

        max_n = config.max_articles_per_digest if config and config.max_articles_per_digest else None
        articles = all_pending[:max_n] if max_n else all_pending
    else:
        all_pending = articles

    if not articles:
        return None

    subject_tmpl = (config.subject_template if config and config.subject_template
                    else "{{tenant_name}} — News Digest {{date}}")
    subject = (subject_tmpl
               .replace("{{tenant_name}}", tenant.name)
               .replace("{{date}}", datetime.datetime.utcnow().strftime("%B %d, %Y")))

    _UNCATEGORIZED = {"Uncategorized", "Other", "", None}
    groups: dict[str, list] = defaultdict(list)
    for a in articles:
        cat = a.category if a.category and a.category not in _UNCATEGORIZED else "General"
        groups[cat].append(a)

    ordered_cats = sorted(groups.keys(), key=lambda c: (c == "General", c))
    articles_by_category = [(cat, groups[cat]) for cat in ordered_cats]
    has_categories = any(c != "General" for c in groups)

    total_pending = len(all_pending)

    return {
        "tenant_name":              tenant.name,
        "logo_url":                 tenant.logo_url or "",
        "primary_color":            tenant.primary_color or "#0066cc",
        "intro_text":               (config.intro_text if config else "") or "",
        "articles":                 articles,
        "all_pending_articles":     all_pending,
        "total_pending":            total_pending,
        "articles_by_category":     articles_by_category,
        "has_categories":           has_categories,
        "date":                     datetime.datetime.utcnow().strftime("%B %d, %Y"),
        "subject":                  subject,
        "from_email":               config.from_email if config else "",
        "from_name":                config.from_name if config else tenant.name,
        "recipients":               recipients,
        "config":                   config,
    }


def build_narrative_context(tenant_id: int, digest_type: str,
                             summary_text: str, db: Session,
                             label: str = "") -> dict | None:
    """Build context for a monthly/yearly narrative digest email."""
    tenant: Tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return None
    config: EmailConfig = (db.query(EmailConfig)
                           .filter_by(tenant_id=tenant_id)
                           .first())
    if not config or not config.is_active:
        return None
    recipients = json.loads(config.recipients_json or "[]")
    if not recipients:
        return None

    if digest_type == "monthly":
        subject = f"{tenant.name} — Monthly Review {label}"
    else:
        subject = f"{tenant.name} — {label} Year in Review"

    return {
        "tenant_name":   tenant.name,
        "logo_url":      tenant.logo_url or "",
        "primary_color": tenant.primary_color or "#0066cc",
        "summary_text":  summary_text,
        "digest_type":   digest_type,
        "label":         label,
        "subject":       subject,
        "from_email":    config.from_email,
        "from_name":     config.from_name,
        "recipients":    recipients,
        "config":        config,
    }
