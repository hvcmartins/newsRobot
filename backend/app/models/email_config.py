import datetime
import enum
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.database import Base


class EmailFrequency(str, enum.Enum):
    immediate = "immediate"
    daily = "daily"
    weekly = "weekly"


class EmailConfig(Base):
    __tablename__ = "email_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True, nullable=False)
    smtp_host = Column(String(255), nullable=False)
    smtp_port = Column(Integer, default=587, nullable=False)
    smtp_user = Column(String(255), nullable=True)
    smtp_password = Column(String(255), nullable=True)
    from_email = Column(String(255), nullable=False)
    from_name = Column(String(255), nullable=False, default="News Robot")
    recipients_json = Column(Text, nullable=False, default="[]")
    frequency = Column(Enum(EmailFrequency), default=EmailFrequency.daily)
    send_time = Column(String(5), default="08:00")
    lookback_hours = Column(Integer, default=24, nullable=False)
    schedule_overrides = Column(Text, nullable=True)  # JSON: {"monday": 72, ...}
    subject_template = Column(String(500),
                               default="{{tenant_name}} News Digest – {{date}}")
    intro_text = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    send_days = Column(Text, nullable=True)  # JSON: ["mon","wed","fri"] — null = all days
    # Monthly digest
    monthly_digest_enabled = Column(Boolean, default=False, nullable=False)
    monthly_digest_day = Column(Integer, default=1)    # day of month (1-28)
    monthly_digest_time = Column(String(5), default="08:00")
    # Yearly digest
    yearly_digest_enabled = Column(Boolean, default=False, nullable=False)
    yearly_digest_month = Column(Integer, default=1)   # month (1-12)
    yearly_digest_day = Column(Integer, default=1)
    yearly_digest_time = Column(String(5), default="08:00")

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)

    tenant = relationship("Tenant", back_populates="email_config")
