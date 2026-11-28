from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from time import monotonic, sleep

import pytest
from sqlalchemy import event, func, select, text, update
from sqlalchemy.orm import Session

from app.models import Booking, Room

STAY = {"check_in": "2030-06-10", "check_out": "2030-06-13", "guests": 2}


def test_health_and_openapi(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    search = spec["paths"]["/api/rooms/search"]["get"]
    assert {parameter["name"] for parameter in search["parameters"]} == set(STAY)
    booking = spec["paths"]["/api/bookings"]["post"]
    assert set(booking["responses"]) == {"201", "400", "404", "409", "422"}
    assert spec["components"]["schemas"]["BookingStatus"]["enum"] == [
        "PENDING", "CONFIRMED", "CANCELLED"
    ]


@pytest.mark.parametrize(
    "changes",
    [
        {"check_in": "2030-02-30"},
        {"check_in": "2030-06-10T00:00:00"},
        {"check_out": STAY["check_in"]},
        {"check_out": "2030-06-09"},
        {"guests": 0},
        {"guests": -1},
        {"guests": 1.5},
    ],
)
def test_invalid_stay(client, changes):
    stay = STAY | changes
    search = client.get("/api/rooms/search", params=stay)
    booking = client.post("/api/bookings", json={"room_id": 1, **stay})
    for response in (search, booking):
        assert response.status_code == 422
        assert set(response.json()["detail"][0]) == {"loc", "msg", "type"}


def test_booking_rejects_extra_fields_and_string_guest_count(client):
    body = {"room_id": 1, **STAY}
    assert client.post("/api/bookings", json=body | {"guests": "2"}).status_code == 422
    response = client.post("/api/bookings", json=body | {"irrelevant": "ignored-value"})
    assert response.status_code == 422
    assert "ignored-value" not in response.text


def test_search_and_capacity(client, room_id):
    response = client.get("/api/rooms/search", params=STAY)
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": room_id,
            "name": "Standard Twin",
            "category": "standard",
            "capacity": 2,
            "nightly_rate": "25000.50",
        }
    ]
    response = client.get("/api/rooms/search", params=STAY | {"guests": 3})
    assert response.status_code == 200
    assert response.json() == []


def test_search_excludes_booked_room_and_allows_adjacent_stays(client, room_id):
    assert client.post("/api/bookings", json={"room_id": room_id, **STAY}).status_code == 201
    cases = [
        ("2030-06-08", "2030-06-10", True),
        ("2030-06-13", "2030-06-15", True),
        ("2030-06-08", "2030-06-11", False),
        ("2030-06-12", "2030-06-15", False),
        ("2030-06-08", "2030-06-15", False),
        ("2030-06-11", "2030-06-12", False),
    ]
    for check_in, check_out, available in cases:
        response = client.get(
            "/api/rooms/search",
            params={"check_in": check_in, "check_out": check_out, "guests": 2},
        )
        assert response.status_code == 200
        assert [room["id"] for room in response.json()] == ([room_id] if available else [])


def test_room_details(client, room_id):
    response = client.get(f"/api/rooms/{room_id}")
    assert response.status_code == 200
    assert response.json() == {
        "id": room_id,
        "name": "Standard Twin",
        "description": "Two single beds",
        "category": "standard",
        "capacity": 2,
        "nightly_rate": "25000.50",
        "amenities": ["Wi-Fi", "Air conditioning"],
    }
    missing = client.get(f"/api/rooms/{room_id + 1}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Room not found"}


def test_booking_checks_room_and_capacity(client, room_id):
    missing = client.post("/api/bookings", json={"room_id": room_id + 1, **STAY})
    assert missing.status_code == 404
    too_many = client.post("/api/bookings", json={"room_id": room_id, **STAY, "guests": 3})
    assert too_many.status_code == 400


def test_booking_saves_price_snapshot(client, database, room_id):
    response = client.post("/api/bookings", json={"room_id": room_id, **STAY})
    assert response.status_code == 201
    created = response.json()
    booking_id = created["id"]
    assert len(created.pop("access_token")) == 43
    assert created == {
        "id": booking_id,
        "room_id": room_id,
        "status": "PENDING",
        "total_price": "75001.50",
        **STAY,
    }

    with database.begin() as connection:
        connection.execute(
            update(Room).where(Room.id == room_id).values(nightly_rate=Decimal("30000.00"))
        )
    with Session(database) as session:
        booking = session.get(Booking, booking_id)
        assert booking.total_price == Decimal("75001.50")
        assert booking.status == "PENDING"


def test_booking_rejects_overlap_and_allows_same_day_turnover(client, room_id):
    body = {"room_id": room_id, **STAY}
    assert client.post("/api/bookings", json=body).status_code == 201
    conflict = client.post("/api/bookings", json=body | {"check_in": "2030-06-12"})
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "Room is unavailable for the selected dates"}
    adjacent = client.post(
        "/api/bookings",
        json=body | {"check_in": STAY["check_out"], "check_out": "2030-06-14"},
    )
    assert adjacent.status_code == 201


def test_booking_rolls_back_after_insert(client, database, room_id):
    def fail_after_flush(_session, _context):
        raise RuntimeError("Injected failure after the INSERT")

    factory = client.app.state.session_factory
    event.listen(factory, "after_flush_postexec", fail_after_flush)
    body = {"room_id": room_id, **STAY}
    try:
        with pytest.raises(RuntimeError, match="Injected failure after the INSERT"):
            client.post("/api/bookings", json=body)
    finally:
        event.remove(factory, "after_flush_postexec", fail_after_flush)

    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(Booking)) == 0
    assert client.post("/api/bookings", json=body).status_code == 201


def test_concurrent_booking_requests(client, database, room_id):
    body = {"room_id": room_id, **STAY}
    waiting_for_room = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() AND wait_event_type = 'Lock' "
        "AND query LIKE '%FROM rooms%' AND query LIKE '%FOR UPDATE%'"
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        with database.begin() as blocker, database.connect() as observer:
            observer = observer.execution_options(isolation_level="AUTOCOMMIT")
            blocker.execute(select(Room.id).where(Room.id == room_id).with_for_update())
            first = pool.submit(client.post, "/api/bookings", json=body)
            second = pool.submit(
                client.post, "/api/bookings", json=body | {"check_in": "2030-06-12"}
            )

            deadline = monotonic() + 10
            while observer.scalar(waiting_for_room) < 2:
                if monotonic() >= deadline:
                    pytest.fail("Both API transactions must be waiting for the room lock")
                sleep(0.02)

        status_codes = [future.result(timeout=10).status_code for future in (first, second)]
        assert sorted(status_codes) == [201, 409]

    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(Booking)) == 1
