from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas import (
    BookingCreate,
    BookingCreatedResponse,
    BookingStateResponse,
    DemoPaymentRequest,
    ErrorResponse,
    PositiveInteger,
    ValidationErrorResponse,
)
from app.services import (
    BookingConflict,
    BookingNotFound,
    BookingService,
    RoomCapacityExceeded,
    RoomNotFound,
    RoomUnavailable,
)

# Public HTTP header name used for CORS and API authentication.
BOOKING_TOKEN_HEADER = "X-Booking-Access-Token"  # nosec B105
NO_STORE = {"Cache-Control": "no-store"}
ACCESS_ERROR = {"model": ErrorResponse, "description": "Booking not found or token invalid"}


def disable_cache(response: Response) -> None:
    response.headers.update(NO_STORE)


def get_booking_service(request: Request) -> BookingService:
    return request.app.state.booking_service


async def booking_not_found(_request: Request, error: BookingNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)}, headers=NO_STORE)


async def booking_conflict(_request: Request, error: BookingConflict) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(error)}, headers=NO_STORE)


router = APIRouter(
    prefix="/api/bookings",
    tags=["bookings"],
    dependencies=[Depends(disable_cache)],
    responses={422: {"model": ValidationErrorResponse, "description": "Invalid booking input"}},
)
BookingId = Annotated[PositiveInteger, Path()]
SessionDependency = Annotated[Session, Depends(get_session)]
BookingServiceDependency = Annotated[BookingService, Depends(get_booking_service)]
BookingToken = Annotated[
    str | None,
    Security(
        APIKeyHeader(name=BOOKING_TOKEN_HEADER, scheme_name="BookingAccessToken", auto_error=False)
    ),
]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=BookingCreatedResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Guest count exceeds room capacity"},
        404: {"model": ErrorResponse, "description": "Room not found"},
        409: {"model": ErrorResponse, "description": "Room unavailable for the selected dates"},
    },
)
def book_room(
    booking: BookingCreate,
    session: SessionDependency,
    service: BookingServiceDependency,
) -> BookingCreatedResponse:
    try:
        return service.create(session, booking)
    except RoomNotFound as error:
        raise HTTPException(404, str(error)) from error
    except RoomCapacityExceeded as error:
        raise HTTPException(400, str(error)) from error
    except RoomUnavailable as error:
        raise HTTPException(409, str(error)) from error


@router.get("/{booking_id}", response_model=BookingStateResponse, responses={404: ACCESS_ERROR})
def get_booking(
    booking_id: BookingId,
    token: BookingToken,
    session: SessionDependency,
    service: BookingServiceDependency,
) -> BookingStateResponse:
    return service.get(session, booking_id, token)


@router.post(
    "/{booking_id}/payment",
    response_model=BookingStateResponse,
    responses={
        404: ACCESS_ERROR,
        409: {"model": ErrorResponse, "description": "Payment conflicts with the booking state"},
    },
)
def pay_booking(
    booking_id: BookingId,
    payment: DemoPaymentRequest,
    token: BookingToken,
    session: SessionDependency,
    service: BookingServiceDependency,
) -> BookingStateResponse:
    return service.pay(session, booking_id, token, payment.outcome)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingStateResponse,
    responses={
        404: ACCESS_ERROR,
        409: {"model": ErrorResponse, "description": "Cancellation conflicts with the booking state"},
    },
)
def cancel_booking(
    booking_id: BookingId,
    token: BookingToken,
    session: SessionDependency,
    service: BookingServiceDependency,
) -> BookingStateResponse:
    return service.cancel(session, booking_id, token)
