from alembic import context
from sqlalchemy import Connection

from app.config import Settings
from app.database import make_engine
from app.models import Base


def run_online(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=str(Settings().database_url),
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        run_online(connection)
    else:
        engine = make_engine(str(Settings().database_url))
        try:
            with engine.connect() as connection:
                run_online(connection)
        finally:
            engine.dispose()
