from typing import Optional
from pydantic import BaseModel
from app.models.email_config import EmailFrequency
from .base import ORMBase, UTCDatetime


class EmailConfigBase(BaseModel):
    tenant_id: int
    smtp_host: str
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: str
    from_name: str = "News Robot"
    recipients_json: str = "[]"
    frequency: EmailFrequency = EmailFrequency.daily
    send_time: str = "08:00"
    lookback_hours: int = 24
    schedule_overrides: Optional[str] = None  # JSON: {"monday": 72, ...}
    subject_template: str = "{{tenant_name}} News Digest – {{date}}"
    intro_text: Optional[str] = None
    is_active: bool = True
    send_days: Optional[str] = None  # JSON: ["mon","wed","fri"]
    max_articles_per_digest: Optional[int] = None  # null = all pending
    monthly_digest_enabled: bool = False
    monthly_digest_day: int = 1
    monthly_digest_time: str = "08:00"
    yearly_digest_enabled: bool = False
    yearly_digest_month: int = 1
    yearly_digest_day: int = 1
    yearly_digest_time: str = "08:00"


class EmailConfigCreate(EmailConfigBase):
    pass


class EmailConfigUpdate(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    recipients_json: Optional[str] = None
    frequency: Optional[EmailFrequency] = None
    send_time: Optional[str] = None
    lookback_hours: Optional[int] = None
    schedule_overrides: Optional[str] = None
    subject_template: Optional[str] = None
    intro_text: Optional[str] = None
    is_active: Optional[bool] = None
    send_days: Optional[str] = None
    max_articles_per_digest: Optional[int] = None
    monthly_digest_enabled: Optional[bool] = None
    monthly_digest_day: Optional[int] = None
    monthly_digest_time: Optional[str] = None
    yearly_digest_enabled: Optional[bool] = None
    yearly_digest_month: Optional[int] = None
    yearly_digest_day: Optional[int] = None
    yearly_digest_time: Optional[str] = None


class EmailConfigRead(EmailConfigBase, ORMBase):
    id: int
    smtp_password: Optional[str] = None  # masked in responses
    created_at: UTCDatetime
    updated_at: UTCDatetime
