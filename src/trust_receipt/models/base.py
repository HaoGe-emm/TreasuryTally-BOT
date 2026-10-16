"""Shared strict primitives for provider-independent domain models."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, StrictStr


def _parse_datetime(value: Any) -> Any:
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("datetime must be timezone-aware UTC")
    return value


class DomainModel(BaseModel):
    """Immutable domain base that rejects silent supplier field drift."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


Identifier = Annotated[StrictStr, Field(min_length=1, max_length=200)]
NonEmptyText = Annotated[StrictStr, Field(min_length=1)]
EvmAddress = Annotated[StrictStr, Field(pattern=r"^0x[0-9a-fA-F]{40}$")]
Hex32 = Annotated[StrictStr, Field(pattern=r"^0x[0-9a-fA-F]{64}$")]
DecimalIntegerString = Annotated[StrictStr, Field(pattern=r"^(0|[1-9][0-9]*)$")]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
PositiveInt = Annotated[StrictInt, Field(gt=0)]
UtcDatetime = Annotated[datetime, BeforeValidator(_parse_datetime), AfterValidator(_require_utc)]
EventKey = tuple[PositiveInt, Hex32, NonNegativeInt]
