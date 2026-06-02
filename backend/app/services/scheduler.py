import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def _make_scrape_job(tenant_id: int):
    def job():
        from app.database import SessionLocal
        from app.services.scraper.runner import run_all_sources
        from app.models import Tenant
        db = SessionLocal()
        try:
            tenant = db.get(Tenant, tenant_id)
            if not tenant:
                return
            if getattr(tenant, 'scrape_paused', False):
                logger.info("Scrape skipped — paused for '%s'", tenant.name)
                return
            logger.info("Scheduled scrape triggered for '%s'", tenant.name)
            run_all_sources(tenant_id, db)
            logger.info("Scheduled scrape complete for '%s'", tenant.name)
        except Exception as exc:
            logger.error("Scheduled scrape failed for tenant %d: %s", tenant_id, exc)
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


def _make_monthly_job(tenant_id: int):
    def job():
        import datetime
        from app.database import SessionLocal
        from app.services.email.monthly_digest import run_monthly_digest
        db = SessionLocal()
        try:
            now = datetime.datetime.utcnow()
            # Send digest for the previous month
            first_of_month = now.replace(day=1)
            prev = first_of_month - datetime.timedelta(days=1)
            run_monthly_digest(tenant_id, prev.year, prev.month, db)
        except Exception as exc:
            logger.error("Monthly digest failed for tenant %d: %s", tenant_id, exc)
        finally:
            db.close()
    return job


def _make_yearly_job(tenant_id: int):
    def job():
        import datetime
        from app.database import SessionLocal
        from app.services.email.monthly_digest import run_yearly_digest
        db = SessionLocal()
        try:
            now = datetime.datetime.utcnow()
            run_yearly_digest(tenant_id, now.year - 1, db)
        except Exception as exc:
            logger.error("Yearly digest failed for tenant %d: %s", tenant_id, exc)
        finally:
            db.close()
    return job


def _add_monthly_job(tenant_id: int, day: int, send_time: str):
    try:
        h, m = send_time.split(":")
        trigger = CronTrigger(day=day, hour=int(h), minute=int(m), timezone="UTC")
        scheduler.add_job(
            _make_monthly_job(tenant_id), trigger=trigger,
            id=f"monthly_{tenant_id}", replace_existing=True,
        )
    except Exception as exc:
        logger.error("Failed to add monthly job for tenant %d: %s", tenant_id, exc)


def _add_yearly_job(tenant_id: int, month: int, day: int, send_time: str):
    try:
        h, m = send_time.split(":")
        trigger = CronTrigger(month=month, day=day, hour=int(h),
                              minute=int(m), timezone="UTC")
        scheduler.add_job(
            _make_yearly_job(tenant_id), trigger=trigger,
            id=f"yearly_{tenant_id}", replace_existing=True,
        )
    except Exception as exc:
        logger.error("Failed to add yearly job for tenant %d: %s", tenant_id, exc)


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
                    _add_email_job(tenant.id, cfg.frequency, cfg.send_time,
                                   getattr(cfg, 'send_days', None))
                if cfg.monthly_digest_enabled:
                    _add_monthly_job(tenant.id, cfg.monthly_digest_day,
                                     cfg.monthly_digest_time)
                if cfg.yearly_digest_enabled:
                    _add_yearly_job(tenant.id, cfg.yearly_digest_month,
                                    cfg.yearly_digest_day, cfg.yearly_digest_time)
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


def _add_email_job(tenant_id: int, frequency: str, send_time: str, send_days: str | None = None):
    try:
        import json as _json
        h, m = send_time.split(":")
        days: list | None = None
        if send_days:
            try:
                days = _json.loads(send_days)
            except Exception:
                pass
        if days:
            trigger = CronTrigger(day_of_week=",".join(days),
                                  hour=int(h), minute=int(m), timezone="UTC")
        elif frequency == "daily":
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
        for jid in (f"scrape_{tenant_id}", f"email_{tenant_id}",
                    f"monthly_{tenant_id}", f"yearly_{tenant_id}"):
            if scheduler.get_job(jid):
                scheduler.remove_job(jid)
        _add_scrape_job(tenant_id, tenant.schedule_cron)
        cfg = tenant.email_config
        if cfg and cfg.is_active:
            if cfg.frequency != EmailFrequency.immediate:
                _add_email_job(tenant_id, cfg.frequency, cfg.send_time,
                               getattr(cfg, 'send_days', None))
            if cfg.monthly_digest_enabled:
                _add_monthly_job(tenant_id, cfg.monthly_digest_day,
                                 cfg.monthly_digest_time)
            if cfg.yearly_digest_enabled:
                _add_yearly_job(tenant_id, cfg.yearly_digest_month,
                                cfg.yearly_digest_day, cfg.yearly_digest_time)
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
