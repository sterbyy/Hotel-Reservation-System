import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.models import BookingStatus, PaymentStatus

logger = logging.getLogger(__name__)


class BookingEventType(StrEnum):
    CREATED = "CREATED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class BookingEvent:
    kind: BookingEventType
    booking_id: int
    status: BookingStatus
    payment_status: PaymentStatus | None


class BookingSubscriber(Protocol):
    def notify(self, event: BookingEvent) -> None: ...


class AuditSubscriber:
    def notify(self, event: BookingEvent) -> None:
        logging.getLogger("uvicorn.error.booking.audit").info(
            "event=%s booking_id=%d status=%s payment_status=%s",
            event.kind,
            event.booking_id,
            event.status,
            event.payment_status,
        )


class DemoNotificationSubscriber:
    def notify(self, event: BookingEvent) -> None:
        logging.getLogger("uvicorn.error.booking.notification").info(
            "demo_notification=%s booking_id=%d", event.kind, event.booking_id
        )


class BookingEventPublisher:
    def __init__(self, subscribers: tuple[BookingSubscriber, ...]):
        self.subscribers = subscribers

    def publish(self, event: BookingEvent) -> None:
        for subscriber in self.subscribers:
            try:
                subscriber.notify(event)
            except Exception:
                logger.error(
                    "Booking observer %s failed for event=%s booking_id=%d",
                    type(subscriber).__name__,
                    event.kind,
                    event.booking_id,
                )
