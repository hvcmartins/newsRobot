import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def _make_scrape_job(tenant_id: int):
    def job():
        from app.database import SessionLocal
        from app.services.scraper.runner import run_all_sources
        db = SessionLocal()
        try:
            logger.info("Scheduler: scraping tenant %d", tenant_id)
            run_all_sources(tenant_id, db)
        except Exception as exc:
            logger.error("Scheduler: scrape failed for tenant %d: %s", tenant_id, exc)
        finally:
            db.close()
    return job


def _make_email_job(tenant_id: int, frequency: str):
    def job():
        from app.database import SessionLocal
        from app.services.email.sender import send_digest_if_configured
        db = SessionLocal()
        try:
            send_digest_if_configured(tenant_id, articles=None,
                                      frequency=frequency, db=db)
        except Exception as exc:
            logger.error("Scheduler: email failed for tenant %d: %s", tenant_id, exc)
        finally:
            db.close()
    return job


def load_tenant_jobs():
    from app.database import SessionLocal
    from app.models import Tenant, EmailFrequency
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        for tenant in tenants:
            _add_scrape_job(tenant.id, tenant.schedule_cron)
            if tenant.email_config and tenant.email_config.is_active:
                cfg = tenant.email_config
                if cfg.frequency != EmailFrequency.immediate:
                    _add_email_job(tenant.id, cfg.frequency, cfg.send_time)
    except Exception as exc:
        logger.error("Failed to load tenant jobs: %s", exc)
    finally:
        db.close()


def _add_scrape_job(tenant_id: int, cron: str):
    try:
        scheduler.add_job(
            _make_scrape_job(tenant_id),
            trigger=CronTrigger.from_crontab(cron, timezone="UTC"),
            id=f"scrape_{tenant_id}",
            replace_existing=True,
            misfire_grace_time=300,
        )
    except Exception as exc:
        logger.error("Failed to add scrape job for tenant %d: %s", tenant_id, exc)


def _add_email_job(tenant_id: int, frequency: str, send_time: str):
    try:
        h, m = send_time.split(":")
        if frequency == "daily":
            trigger = CronTrigger(hour=int(h), minute=int(m), timezone="UTC")
        else:
            trigger = CronTrigger(day_of_week="mon", hour=int(h),
                                  minute=int(m), timezone="UTC")
        scheduler.add_job(
            _make_email_job(tenant_id, frequency),
            trigger=trigger,
            id=f"email_{tenant_id}",
            replace_existing=True,
        )
    except Exception as exc:
        logger.error("Failed to add email job for tenant %d: %s", tenant_id, exc)


def refresh_tenant_job(tenant_id: int):
    from app.database import SessionLocal
    from app.models import EmailFrequency
    db = SessionLocal()
    try:
        from app.models import Tenant
        tenant = db.get(Tenant, tenant_id)
        if not tenant:
            return
        for jid in (f"scrape_{tenant_id}", f"email_{tenant_id}"):
            if scheduler.get_job(jid):
                scheduler.remove_job(jid)
        _add_scrape_job(tenant_id, tenant.schedule_cron)
        cfg = tenant.email_config
        if cfg and cfg.is_active and cfg.frequency != EmailFrequency.immediate:
            _add_email_job(tenant_id, cfg.frequency, cfg.send_time)
    finally:
        db.close()


def start_scheduler():
    load_tenant_jobs()
    scheduler.start()
    logger.info("APScheduler started")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")
