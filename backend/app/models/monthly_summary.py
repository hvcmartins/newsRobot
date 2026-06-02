import datetime
from sqlalchemy import (Column, Integer, Text, DateTime, ForeignKey,
                        UniqueConstraint, Index)
from app.database import Base


class MonthlySummary(Base):
    __tablename__ = "monthly_summaries"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
                       nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    summary_text = Column(Text, nullable=True)
    digest_id = Column(Integer,
                       ForeignKey("sent_digests.id", ondelete="SET NULL"),
                       nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "year", "month", name="uq_monthly_summary"),
        Index("ix_monthly_summary_tenant", "tenant_id"),
    )
