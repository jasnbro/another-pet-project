import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so they're registered on db.metadata before Alembic
# compares it against the database -- this module lives alongside
# models.py/db.py (see alembic.ini's prepend_sys_path), matching how
# app.py/seed.py/tests import them (flat, no package prefix).
import models  # noqa: E402,F401  (populates db.metadata as a side effect)
from db import db  # noqa: E402

target_metadata = db.metadata

# The database URL always comes from DATABASE_URL (same variable the Flask
# app itself reads in app.py) -- never from alembic.ini, so one env var
# controls both the app and its migrations and there's no risk of them
# pointing at different databases. Deliberately no sqlite fallback here:
# migrations are authored/tested against Postgres, the production target,
# and generating them against sqlite could silently emit the wrong dialect
# (e.g. CHECK constraint syntax, ARRAY-adjacent types).
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not set. Alembic needs it to know which database "
        "to migrate -- e.g.:\n"
        "  export DATABASE_URL=postgresql://mindless_meals:<password>@localhost:5432/mindless_meals\n"
        "See mindless_meals/docs/database.md for local setup."
    )
config.set_main_option("sqlalchemy.url", database_url)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
