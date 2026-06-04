import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, BeforeValidator


def _to_utc(v: datetime.datetime) -> datetime.datetime:
    if isinstance(v, datetime.datetime) and v.tzinfo is None:
        return v.replace(tzinfo=datetime.timezone.utc)
    return v


# Use this type for all datetime fields in Read schemas.
# SQLAlchemy returns naive UTC datetimes; this validator attaches UTC tzinfo
# so Pydantic serializes them as "...+00:00" — browsers then parse correctly.
UTCDatetime = Annotated[datetime.datetime, BeforeValidator(_to_utc)]


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
