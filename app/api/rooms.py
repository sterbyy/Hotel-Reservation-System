from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Room
from app.repositories import RoomRepository
from app.schemas import (
    ErrorResponse,
    PositiveInteger,
    RoomDetails,
    RoomSummary,
    Stay,
    ValidationErrorResponse,
)

router = APIRouter(
    prefix="/api/rooms",
    tags=["rooms"],
    responses={422: {"model": ValidationErrorResponse, "description": "Invalid parameters"}},
)


@router.get(
    "/search",
    response_model=list[RoomSummary],
    description="Find rooms free for the full stay. The check-out date is exclusive.",
)
def search_rooms(
    stay: Annotated[Stay, Query()],
    session: Annotated[Session, Depends(get_session)],
) -> Sequence[Room]:
    return RoomRepository(session).search(stay.check_in, stay.check_out, stay.guests)


@router.get(
    "/{room_id}",
    response_model=RoomDetails,
    responses={404: {"model": ErrorResponse, "description": "Room not found"}},
)
def room_details(
    room_id: Annotated[PositiveInteger, Path()],
    session: Annotated[Session, Depends(get_session)],
) -> Room:
    room = RoomRepository(session).get(room_id)
    if room is None:
        raise HTTPException(404, "Room not found")
    return room
