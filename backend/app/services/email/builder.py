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

    # For real sends, require an active config with recipients
    if not preview:
        if not config or not config.is_active:
            return None
        recipients = json.loads(config.recipients_json or "[]")
        if not recipients:
            return None
    else:
        recipients = json.loads(config.recipients_json or "[]") if config else []

    if articles is None:
        cutoff = {
            "daily":  datetime.datetime.utcnow() - datetime.timedelta(days=1),
            "weekly": datetime.datetime.utcnow() - datetime.timedelta(days=7),
        }.get(frequency)

        query = (db.query(Article)
                 .filter(Article.tenant_id == tenant_id,
                         Article.duplicate_of_id.is_(None)))
        if cutoff:
            query = query.filter(Article.scraped_at >= cutoff)
        articles = (query
                    .order_by(Article.relevance_score.desc(),
                              Article.published_at.desc())
                    .limit(20)
                    .all())

    if not articles:
        return None

    subject_tmpl = (config.subject_template if config and config.subject_template
                    else "{{tenant_name}} — News Digest {{date}}")
    subject = (subject_tmpl
               .replace("{{tenant_name}}", tenant.name)
               .replace("{{date}}", datetime.datetime.utcnow().strftime("%B %d, %Y")))

    # Group by AI-assigned category for the template
    _UNCATEGORIZED = {"Uncategorized", "Other", "", None}
    groups: dict[str, list] = defaultdict(list)
    for a in articles:
        cat = a.category if a.category and a.category not in _UNCATEGORIZED else "General"
        groups[cat].append(a)

    # Real categories first (sorted), "General" last
    ordered_cats = sorted(groups.keys(), key=lambda c: (c == "General", c))
    articles_by_category = [(cat, groups[cat]) for cat in ordered_cats]

    # Only show category headers when at least one named category exists
    has_categories = any(c != "General" for c in groups)

    return {
        "tenant_name":          tenant.name,
        "logo_url":             tenant.logo_url or "",
        "primary_color":        tenant.primary_color or "#0066cc",
        "intro_text":           (config.intro_text if config else "") or "",
        "articles":             articles,
        "articles_by_category": articles_by_category,
        "has_categories":       has_categories,
        "date":                 datetime.datetime.utcnow().strftime("%B %d, %Y"),
        "subject":              subject,
        "from_email":           config.from_email if config else "",
        "from_name":            config.from_name if config else tenant.name,
        "recipients":           recipients,
        "config":               config,
    }
