from typing import Optional
from pydantic import BaseModel, ConfigDict
import datetime
from app.models.email_config import EmailFrequency


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


class EmailConfigRead(EmailConfigBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    smtp_password: Optional[str] = None  # masked in responses
    created_at: datetime.datetime
    updated_at: datetime.datetime
