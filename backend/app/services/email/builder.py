import datetime
import json
import logging
from sqlalchemy.orm import Session

from app.models import Tenant, EmailConfig, Article, EmailFrequency

logger = logging.getLogger(__name__)


def build_email_context(tenant_id: int, articles: list | None,
                         frequency: str, db: Session) -> dict | None:
    tenant: Tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return None

    config: EmailConfig = (db.query(EmailConfig)
                           .filter_by(tenant_id=tenant_id, is_active=True)
                           .first())
    if not config:
        return None

    recipients = json.loads(config.recipients_json or "[]")
    if not recipients:
        return None

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

    subject = (config.subject_template
               .replace("{{tenant_name}}", tenant.name)
               .replace("{{date}}", datetime.datetime.utcnow().strftime("%B %d, %Y")))

    return {
        "tenant_name":   tenant.name,
        "logo_url":      tenant.logo_url or "",
        "primary_color": tenant.primary_color or "#0066cc",
        "intro_text":    config.intro_text or "",
        "articles":      articles,
        "date":          datetime.datetime.utcnow().strftime("%B %d, %Y"),
        "subject":       subject,
        "from_email":    config.from_email,
        "from_name":     config.from_name,
        "recipients":    recipients,
        "config":        config,
    }
