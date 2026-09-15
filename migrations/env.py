from alembic import context
from sqlalchemy import create_engine, event

from bot.db.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(config.get_main_option("sqlalchemy.url"))

    # pysqlite commits DDL immediately, so a failing migration would leave half-created tables behind.
    # Taking over transaction control makes each migration run all-or-nothing.
    @event.listens_for(engine, "connect")
    def _disable_pysqlite_transactions(dbapi_connection, _record) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(connection) -> None:
        connection.exec_driver_sql("BEGIN")

    with engine.connect() as connection:
        # Batch mode is required for ALTER TABLE on SQLite.
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True, transactional_ddl=True
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
