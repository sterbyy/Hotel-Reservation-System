import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from time import monotonic, sleep
from unittest.mock import patch

import pytest
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.orm import Session

from app.booking_events import AuditSubscriber, BookingEventType
from app.main import create_app
from app.models import Booking, Payment, Room
from app.payments import DemoPaymentSimulator

CHECK_IN = date(2030, 6, 10)
STAY = {"check_in": CHECK_IN.isoformat(), "check_out": "2030-06-13", "guests": 2}
HEADER = "X-Booking-Access-Token"
AUDIT = "uvicorn.error.booking.audit"
NOTIFICATION = "uvicorn.error.booking.notification"


@pytest.fixture
def clock(client, monkeypatch):
    def set_days_before_check_in(days):
        monkeypatch.setattr(
            client.app.state.booking_service, "today", lambda: CHECK_IN - timedelta(days=days)
        )

    set_days_before_check_in(2)
    return set_days_before_check_in


@pytest.fixture
def booking(client, room_id, clock):
    response = client.post("/api/bookings", json={"room_id": room_id, **STAY})
    assert response.status_code == 201
    data = response.json()
    return f"/api/bookings/{data['id']}", {HEADER: data["access_token"]}, data


def test_migrations_create_lifecycle_schema(database):
    with database.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == "0002_booking_lifecycle"
        schema = inspect(connection)
        assert {"rooms", "bookings", "payments", "alembic_version"} <= set(schema.get_table_names())
        assert schema.get_pk_constraint("payments")["constrained_columns"] == ["booking_id"]
        assert schema.get_foreign_keys("payments")[0]["referred_table"] == "bookings"


def test_booking_token_is_returned_once_and_only_digest_is_stored(client, database, room_id):
    first = client.post("/api/bookings", json={"room_id": room_id, **STAY})
    assert first.status_code == 201
    assert first.headers["cache-control"] == "no-store"
    created = first.json()
    token = created.pop("access_token")
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)

    with Session(database) as session:
        row = session.get(Booking, created["id"])
        assert row.access_token_hash == hashlib.sha256(token.encode("ascii")).digest()
        assert row.access_token_hash != token.encode("ascii")

    adjacent = {"check_in": STAY["check_out"], "check_out": "2030-06-14", "guests": 2}
    second = client.post("/api/bookings", json={"room_id": room_id, **adjacent})
    assert second.status_code == 201
    assert second.json()["access_token"] != token
    cross_access = client.get(
        f"/api/bookings/{created['id']}", headers={HEADER: second.json()["access_token"]}
    )
    assert cross_access.status_code == 404

    response = client.get(f"/api/bookings/{created['id']}", headers={HEADER: token})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == created | {"payment": None}


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [("GET", "", None), ("POST", "/payment", {"outcome": "SUCCEEDED"}), ("POST", "/cancel", None)],
)
def test_protected_routes_hide_booking_existence(client, booking, method, suffix, body):
    url, headers, created = booking
    wrong = "A" * 43 if headers[HEADER] != "A" * 43 else "B" * 43
    for book_url, auth in [
        (url, {}),
        (url, {HEADER: wrong}),
        (url, {HEADER: "short"}),
        (f"/api/bookings/{created['id'] + 1}", headers),
    ]:
        response = client.request(method, book_url + suffix, headers=auth, json=body)
        assert response.status_code == 404
        assert response.json() == {"detail": "Booking not found"}
        assert response.headers["cache-control"] == "no-store"

    assert client.get(url, headers=headers).json()["status"] == "PENDING"
    assert client.get(url, headers=headers).json()["payment"] is None


def test_lifecycle_openapi_and_cors(postgres):
    _, settings = postgres
    origin = "http://localhost:5173"
    settings = settings.model_copy(update={"cors_origins": origin})
    with TestClient(create_app(settings)) as client:
        spec = client.get("/openapi.json").json()
        assert spec["components"]["securitySchemes"]["BookingAccessToken"] == {
            "type": "apiKey", "in": "header", "name": HEADER
        }
        for suffix, method in (("", "get"), ("/payment", "post"), ("/cancel", "post")):
            assert spec["paths"][f"/api/bookings/{{booking_id}}{suffix}"][method]["security"] == [
                {"BookingAccessToken": []}
            ]
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": f"content-type, {HEADER}",
        }
        response = client.options("/api/bookings/1/payment", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert HEADER.lower() in response.headers["access-control-allow-headers"].lower()
        blocked = client.options(
            "/api/bookings/1/payment", headers=headers | {"Origin": "http://localhost:5174"}
        )
        assert blocked.status_code == 400
        assert "access-control-allow-origin" not in blocked.headers


def test_engine_pool_lifecycle_is_isolated_per_application(postgres):
    _, settings = postgres
    disposed = []
    with TestClient(create_app(settings)) as second:
        second_engine = second.app.state.session_factory.kw["bind"]
        event.listen(second_engine, "engine_disposed", lambda engine: disposed.append(engine))
        with TestClient(create_app(settings)) as first:
            first_engine = first.app.state.session_factory.kw["bind"]
            event.listen(first_engine, "engine_disposed", lambda engine: disposed.append(engine))
            assert first_engine is not second_engine
            assert first_engine.pool is not second_engine.pool
            assert first.get("/health").status_code == 200
        assert disposed == [first_engine]
        assert second.get("/health").status_code == 200
    assert disposed == [first_engine, second_engine]


def test_payment_decline_retry_success_and_replays(client, database, booking):
    url, headers, data = booking
    with patch.object(
        DemoPaymentSimulator, "settle", autospec=True, side_effect=DemoPaymentSimulator.settle
    ) as charge:
        invalid = client.post(
            url + "/payment", headers=headers, json={"outcome": "SUCCEEDED", "extra": "unused"}
        )
        assert invalid.status_code == 422
        failed = {"outcome": "FAILED"}
        declined = client.post(url + "/payment", headers=headers, json=failed)
        assert declined.status_code == 200
        assert declined.json()["status"] == "PENDING"
        assert declined.json()["payment"] == {"status": "FAILED", "refunded_amount": None}
        assert client.post(url + "/payment", headers=headers, json=failed).json() == declined.json()

        succeeded = {"outcome": "SUCCEEDED"}
        paid = client.post(url + "/payment", headers=headers, json=succeeded)
        assert paid.status_code == 200
        assert paid.json()["status"] == "CONFIRMED"
        assert paid.json()["payment"] == {"status": "SUCCEEDED", "refunded_amount": None}
        assert paid.json()["total_price"] == data["total_price"]
        assert "access_token" not in paid.json()
        assert client.post(url + "/payment", headers=headers, json=succeeded).json() == paid.json()
        assert client.post(url + "/payment", headers=headers, json=failed).status_code == 409
        assert charge.call_count == 2
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(Payment)) == 1


def test_cancelling_after_a_decline_keeps_the_failed_payment(client, booking):
    url, headers, _ = booking
    assert client.post(url + "/payment", headers=headers, json={"outcome": "FAILED"}).status_code == 200
    result = client.post(url + "/cancel", headers=headers)
    assert result.status_code == 200
    assert result.json()["status"] == "CANCELLED"
    assert result.json()["payment"] == {"status": "FAILED", "refunded_amount": None}


def test_payment_and_cancel_lock_the_room_before_the_booking(client, booking):
    url, headers, _ = booking
    engine = client.app.state.session_factory.kw["bind"]
    locks = []

    def collect_locks(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "FOR UPDATE" in statement:
            locks.append(statement)

    event.listen(engine, "before_cursor_execute", collect_locks)
    try:
        paid = client.post(url + "/payment", headers=headers, json={"outcome": "SUCCEEDED"})
        cancelled = client.post(url + "/cancel", headers=headers)
    finally:
        event.remove(engine, "before_cursor_execute", collect_locks)

    assert paid.status_code == cancelled.status_code == 200
    assert len(locks) == 4
    for room_lock, booking_lock in ((locks[0], locks[1]), (locks[2], locks[3])):
        assert "FROM rooms" in room_lock and "FOR UPDATE OF rooms" in room_lock
        assert "FROM bookings" in booking_lock


@pytest.mark.parametrize(
    ("paid", "days", "expected_status", "payment_status", "refund"),
    [
        (False, 1, 200, None, None),
        (False, 0, 409, None, None),
        (False, -1, 409, None, None),
        (True, 2, 200, "REFUNDED", "75001.50"),
        (True, 1, 200, "SUCCEEDED", None),
        (True, 0, 409, "SUCCEEDED", None),
        (True, -1, 409, "SUCCEEDED", None),
    ],
)
def test_cancellation_policy_boundaries(client, booking, clock, paid, days, expected_status, payment_status, refund):
    url, headers, data = booking
    original_status = "PENDING"
    if paid:
        assert client.post(url + "/payment", headers=headers, json={"outcome": "SUCCEEDED"}).status_code == 200
        original_status = "CONFIRMED"
    assert client.get("/api/rooms/search", params=STAY).json() == []

    clock(days)
    cancelled = client.post(url + "/cancel", headers=headers)
    assert cancelled.status_code == expected_status
    state = client.get(url, headers=headers).json()
    expected_payment = (
        {"status": payment_status, "refunded_amount": refund} if payment_status else None
    )
    assert state["payment"] == expected_payment
    if expected_status == 409:
        assert cancelled.json() == {"detail": "Booking cannot be cancelled on or after check-in"}
        assert state["status"] == original_status
        assert client.get("/api/rooms/search", params=STAY).json() == []
        return

    assert cancelled.json() == state
    assert state["status"] == "CANCELLED"
    assert state["total_price"] == data["total_price"]
    assert [room["id"] for room in client.get("/api/rooms/search", params=STAY).json()] == [
        data["room_id"]
    ]
    clock(-1)
    assert client.post(url + "/cancel", headers=headers).json() == state
    rejected = client.post(url + "/payment", headers=headers, json={"outcome": "SUCCEEDED"})
    assert rejected.status_code == 409
    assert rejected.json() == {"detail": "Cancelled booking cannot be paid"}
    assert client.post("/api/bookings", json={"room_id": data["room_id"], **STAY}).status_code == 201


def test_both_observers_see_committed_state_without_credentials(client, database, room_id, clock, caplog):
    notify = AuditSubscriber.notify

    def audit_after_commit(subscriber, message):
        with Session(database) as session:
            row = session.get(Booking, message.booking_id)
            payment = session.get(Payment, message.booking_id)
            assert row.status == message.status
            assert (payment.status if payment is not None else None) == message.payment_status
        notify(subscriber, message)

    caplog.set_level(logging.INFO)
    with patch.object(AuditSubscriber, "notify", autospec=True, side_effect=audit_after_commit) as audit:
        created = client.post("/api/bookings", json={"room_id": room_id, **STAY}).json()
        url = f"/api/bookings/{created['id']}"
        token = created["access_token"]
        headers = {HEADER: token}
        for outcome in ("FAILED", "FAILED", "SUCCEEDED", "SUCCEEDED"):
            assert client.post(url + "/payment", headers=headers, json={"outcome": outcome}).status_code == 200
        for _ in range(2):
            assert client.post(url + "/cancel", headers=headers).status_code == 200

        message_types = [
            BookingEventType.CREATED,
            BookingEventType.PAYMENT_FAILED,
            BookingEventType.CONFIRMED,
            BookingEventType.CANCELLED,
        ]
        assert [call.args[1].kind for call in audit.call_args_list] == message_types
        for logger in (AUDIT, NOTIFICATION):
            records = [record.getMessage() for record in caplog.records if record.name == logger]
            assert len(records) == len(message_types)
            assert all(kind in message for kind, message in zip(message_types, records, strict=True))
        assert token not in caplog.text
        assert hashlib.sha256(token.encode("ascii")).hexdigest() not in caplog.text


@pytest.mark.parametrize("operation", ["create", "payment", "cancel"])
def test_rollback_publishes_no_observer_events(client, database, room_id, clock, caplog, operation):
    caplog.set_level(logging.INFO)
    body = {"room_id": room_id, **STAY}
    if operation != "create":
        created = client.post("/api/bookings", json=body).json()
        url = f"/api/bookings/{created['id']}"
        headers = {HEADER: created["access_token"]}
        if operation == "cancel":
            assert client.post(url + "/payment", headers=headers, json={"outcome": "SUCCEEDED"}).status_code == 200
        before = client.get(url, headers=headers).json()
    caplog.clear()

    def fail_after_flush(_session, _context):
        raise RuntimeError("Injected lifecycle rollback")

    factory = client.app.state.session_factory
    event.listen(factory, "after_flush_postexec", fail_after_flush)
    try:
        with pytest.raises(RuntimeError, match="Injected lifecycle rollback"):
            if operation == "create":
                client.post("/api/bookings", json=body)
            elif operation == "payment":
                client.post(url + "/payment", headers=headers, json={"outcome": "SUCCEEDED"})
            else:
                client.post(url + "/cancel", headers=headers)
    finally:
        event.remove(factory, "after_flush_postexec", fail_after_flush)

    assert not any(record.name in (AUDIT, NOTIFICATION) for record in caplog.records)
    if operation == "create":
        with Session(database) as session:
            assert session.scalar(select(func.count()).select_from(Booking)) == 0
    else:
        assert client.get(url, headers=headers).json() == before


def race_room_requests(client, database, room_id, requests):
    waiting = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() AND wait_event_type = 'Lock' "
        "AND query LIKE '%FROM rooms%' AND query LIKE '%FOR UPDATE%'"
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        with database.begin() as blocker, database.connect() as observer:
            observer = observer.execution_options(isolation_level="AUTOCOMMIT")
            blocker.execute(select(Room.id).where(Room.id == room_id).with_for_update())
            responses = []
            for url, kwargs in requests:
                responses.append(pool.submit(client.post, url, **kwargs))
                deadline = monotonic() + 10
                while observer.scalar(waiting) < len(responses):
                    if monotonic() >= deadline:
                        pytest.fail("Lifecycle request did not wait on the room lock")
                    sleep(0.02)
        return [response.result(timeout=10) for response in responses]


@pytest.mark.parametrize("first", ["payment", "cancel"])
def test_concurrent_payment_and_cancellation(client, database, booking, first):
    url, headers, data = booking
    requests = {
        "payment": (url + "/payment", {"headers": headers, "json": {"outcome": "SUCCEEDED"}}),
        "cancel": (url + "/cancel", {"headers": headers}),
    }
    order = [first, "cancel" if first == "payment" else "payment"]
    responses = race_room_requests(
        client, database, data["room_id"], [requests[action] for action in order]
    )
    results = dict(zip(order, responses, strict=True))
    paid, cancelled = results["payment"], results["cancel"]
    assert cancelled.status_code == 200
    assert cancelled.json() == client.get(url, headers=headers).json()
    assert cancelled.json()["status"] == "CANCELLED"
    with Session(database) as session:
        payment = session.get(Payment, data["id"])
        if first == "payment":
            assert paid.status_code == 200
            assert paid.json()["status"] == "CONFIRMED"
            assert payment.status == "REFUNDED"
            assert payment.refunded_amount == Decimal(data["total_price"])
        else:
            assert paid.status_code == 409
            assert payment is None


def test_concurrent_cancellations_refund_once(client, database, booking):
    url, headers, data = booking
    assert client.post(url + "/payment", headers=headers, json={"outcome": "SUCCEEDED"}).status_code == 200
    with patch.object(
        DemoPaymentSimulator, "reverse", autospec=True, side_effect=DemoPaymentSimulator.reverse
    ) as refund:
        first, second = race_room_requests(
            client, database, data["room_id"], [(url + "/cancel", {"headers": headers})] * 2
        )
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json() == client.get(url, headers=headers).json()
        assert first.json()["payment"] == {"status": "REFUNDED", "refunded_amount": "75001.50"}
        refund.assert_called_once()


@pytest.mark.parametrize("first", ["create", "cancel"])
def test_concurrent_creation_and_cancellation_use_same_room_lock(client, database, booking, first):
    url, headers, data = booking
    room_id = data["room_id"]
    requests = {
        "create": ("/api/bookings", {"json": {"room_id": room_id, **STAY}}),
        "cancel": (url + "/cancel", {"headers": headers}),
    }
    order = [first, "cancel" if first == "create" else "create"]
    responses = race_room_requests(client, database, room_id, [requests[action] for action in order])
    results = dict(zip(order, responses, strict=True))
    assert results["cancel"].status_code == 200
    assert results["cancel"].json()["status"] == "CANCELLED"
    assert results["create"].status_code == (201 if first == "cancel" else 409)
    with Session(database) as session:
        active_count = session.scalar(
            select(func.count()).select_from(Booking).where(
                Booking.room_id == room_id, Booking.status == "PENDING"
            )
        )
    assert active_count == int(first == "cancel")
