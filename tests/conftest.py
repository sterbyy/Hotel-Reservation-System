import os
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import Settings
from app.database import make_engine
from app.main import create_app
from app.models import Booking, Payment, Room


@pytest.fixture(scope="session")
def postgres():
    test_url = os.environ.get("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated PostgreSQL test database")

    url = make_url(test_url)
    if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must use postgresql+psycopg and a database ending in _test")

    schema = f"hotel_test_{uuid4().hex}"
    admin_engine = make_engine(test_url)
    schema_url = url.update_query_dict({"options": f"-csearch_path={schema}"})
    settings = Settings(database_url=schema_url.render_as_string(hide_password=False))
    engine = make_engine(str(settings.database_url))

    try:
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        try:
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            with engine.connect() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
            yield engine, settings
        finally:
            engine.dispose()
            with admin_engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
    finally:
        admin_engine.dispose()


@pytest.fixture
def database(postgres):
    engine, _ = postgres
    with engine.begin() as connection:
        connection.execute(delete(Payment))
        connection.execute(delete(Booking))
        connection.execute(delete(Room))
    return engine


@pytest.fixture
def client(postgres, database):
    _, settings = postgres
    with TestClient(create_app(settings)) as api_client:
        yield api_client


@pytest.fixture
def room_id(database):
    with Session(database) as session, session.begin():
        room = Room(
            name="Standard Twin",
            description="Two single beds",
            category="standard",
            capacity=2,
            nightly_rate=Decimal("25000.50"),
            amenities=["Wi-Fi", "Air conditioning"],
        )
        session.add(room)
        session.flush()
        return room.id
