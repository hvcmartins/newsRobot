"""Monthly and yearly narrative digest generation and sending."""
import calendar
import datetime
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_LANG_NAMES = {
    "en": "English", "pt": "Portuguese", "fr": "French", "es": "Spanish",
    "de": "German", "it": "Italian", "nl": "Dutch",
}


def _primary_language(tenant) -> str:
    import json
    accepted = json.loads(tenant.accepted_languages or "[]")
    lang = tenant.translation_language or (accepted[0] if accepted else "en")
    return _LANG_NAMES.get(lang, "English")


def run_monthly_digest(tenant_id: int, year: int, month: int, db: Session) -> bool:
    """Generate and send the monthly narrative digest for a given month."""
    from app.models import Tenant, Article
    from app.models.monthly_summary import MonthlySummary
    from app.services.ai.factory import get_ai_provider
    from app.services.ai.null import NullProvider
    from app.services.email.sender import send_narrative_digest

    tenant: Tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return False

    # Check if already sent for this month
    existing = (db.query(MonthlySummary)
                .filter_by(tenant_id=tenant_id, year=year, month=month)
                .first())
    if existing:
        logger.info("Monthly digest already sent for tenant %d %d-%02d", tenant_id, year, month)
        return False

    # Collect archived articles from that month
    start = datetime.datetime(year, month, 1)
    end = datetime.datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)
    articles = (db.query(Article)
                .filter(Article.tenant_id == tenant_id,
                        Article.archived_at >= start,
                        Article.archived_at <= end)
                .order_by(Article.relevance_score.desc())
                .limit(100)
                .all())

    if not articles:
        logger.info("No archived articles for monthly digest (tenant %d %d-%02d)",
                    tenant_id, year, month)
        return False

    # Build article text for the AI prompt
    articles_text = "\n\n".join(
        f"- {a.title}: {a.summary or a.excerpt or ''}"
        for a in articles
    )
    month_label = datetime.date(year, month, 1).strftime("%B %Y")
    language = _primary_language(tenant)

    ai = get_ai_provider()
    if isinstance(ai, NullProvider):
        summary_text = f"Monthly digest for {month_label}: {len(articles)} articles archived."
    else:
        try:
            summary_text = ai.summarize_monthly(
                tenant.name, month_label, articles_text, language
            )
        except Exception as exc:
            logger.error("Monthly digest AI summarization failed: %s", exc)
            return False

    # Store monthly summary
    ms = MonthlySummary(
        tenant_id=tenant_id,
        year=year,
        month=month,
        summary_text=summary_text,
    )
    db.add(ms)
    db.commit()
    db.refresh(ms)

    # Send email
    sent_digest_id = send_narrative_digest(
        tenant_id=tenant_id,
        digest_type="monthly",
        summary_text=summary_text,
        label=month_label,
        db=db,
    )
    if sent_digest_id:
        ms.digest_id = sent_digest_id
        db.commit()

    return bool(sent_digest_id)


def run_yearly_digest(tenant_id: int, year: int, db: Session) -> bool:
    """Generate and send the yearly narrative digest using monthly summaries."""
    from app.models import Tenant
    from app.models.monthly_summary import MonthlySummary
    from app.services.ai.factory import get_ai_provider
    from app.services.ai.null import NullProvider
    from app.services.email.sender import send_narrative_digest

    tenant: Tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return False

    summaries = (db.query(MonthlySummary)
                 .filter_by(tenant_id=tenant_id, year=year)
                 .order_by(MonthlySummary.month)
                 .all())

    if not summaries:
        logger.info("No monthly summaries for yearly digest (tenant %d %d)", tenant_id, year)
        return False

    months_text = "\n\n".join(
        f"## {calendar.month_name[s.month]} {year}\n{s.summary_text or ''}"
        for s in summaries
    )
    language = _primary_language(tenant)

    ai = get_ai_provider()
    if isinstance(ai, NullProvider):
        summary_text = f"Year in review {year}: {len(summaries)} monthly summaries."
    else:
        try:
            summary_text = ai.summarize_yearly(tenant.name, year, months_text, language)
        except Exception as exc:
            logger.error("Yearly digest AI summarization failed: %s", exc)
            return False

    return send_narrative_digest(
        tenant_id=tenant_id,
        digest_type="yearly",
        summary_text=summary_text,
        label=str(year),
        db=db,
    )
