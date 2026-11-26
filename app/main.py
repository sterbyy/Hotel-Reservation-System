from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker

from app.api import bookings, health, rooms
from app.booking_events import AuditSubscriber, BookingEventPublisher, DemoNotificationSubscriber
from app.config import Settings
from app.database import make_engine
from app.payments import DemoPaymentGatewayFactory
from app.schemas import ValidationErrorResponse, ValidationIssue
from app.services import BookingConflict, BookingNotFound, BookingService


def validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
    body = ValidationErrorResponse(
        detail=[
            ValidationIssue(loc=issue["loc"], msg=issue["msg"], type=issue["type"])
            for issue in error.errors()
        ]
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(str(settings.database_url))
        app.state.session_factory = sessionmaker(bind=engine)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Hotel Reservation System", version="0.1.0", lifespan=lifespan)
    app.state.booking_service = BookingService(
        DemoPaymentGatewayFactory(),
        BookingEventPublisher((AuditSubscriber(), DemoNotificationSubscriber())),
    )
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(BookingNotFound, bookings.booking_not_found)
    app.add_exception_handler(BookingConflict, bookings.booking_conflict)
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", bookings.BOOKING_TOKEN_HEADER],
        )
    app.include_router(health.router)
    app.include_router(rooms.router)
    app.include_router(bookings.router)
    return app
