import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.models import BookingStatus, PaymentStatus
from app.payments import DemoPaymentOutcome


def parse_calendar_date(value: object) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError("Use an existing calendar date in YYYY-MM-DD format") from None
    raise ValueError("Use an existing calendar date in YYYY-MM-DD format")


CalendarDate = Annotated[date, BeforeValidator(parse_calendar_date)]
PositiveInteger = Annotated[int, Field(gt=0, le=2_147_483_647)]


class ErrorResponse(BaseModel):
    detail: str


class ValidationIssue(BaseModel):
    loc: tuple[str | int, ...]
    msg: str
    type: str


class ValidationErrorResponse(BaseModel):
    detail: list[ValidationIssue]


class Stay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_in: CalendarDate
    check_out: CalendarDate
    guests: PositiveInteger

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be later than check_in")
        return self


class RoomSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    capacity: int
    nightly_rate: Decimal


class RoomDetails(RoomSummary):
    description: str
    amenities: list[str]


class BookingCreate(Stay):
    room_id: Annotated[PositiveInteger, Field(strict=True)]
    guests: Annotated[PositiveInteger, Field(strict=True)]


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    status: BookingStatus
    check_in: date
    check_out: date
    guests: int
    total_price: Decimal


class BookingCreatedResponse(BookingResponse):
    access_token: str = Field(repr=False, description="Only returned when creating the booking")


class DemoPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: DemoPaymentOutcome


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: PaymentStatus
    refunded_amount: Decimal | None


class BookingStateResponse(BookingResponse):
    payment: PaymentResponse | None
