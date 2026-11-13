"""Run the identity database's migrations: `flask identity migrate`.

Takes a Postgres advisory lock first, so two apps deploying at the same
time can't both migrate the shared identity database at once."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

from .store import Store, metadata

MIGRATIONS = Path(__file__).resolve().parent / "migrations"
LOCK_ID = 7_418_530_244  # arbitrary, fixed: "identity migrations"


def _config(connection) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.attributes["connection"] = connection
    cfg.attributes["metadata"] = metadata
    return cfg


def head() -> str:
    return ScriptDirectory.from_config(_config(None)).get_current_head()


def current(store: Store) -> str | None:
    with store.engine.connect() as conn:
        return MigrationContext.configure(conn, opts={"version_table": "identity_alembic_version"}).get_current_revision()


def upgrade(store: Store) -> tuple[str | None, str]:
    """Returns (revision before, revision after)."""
    with store.engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.exec_driver_sql(f"SELECT pg_advisory_xact_lock({LOCK_ID})")
        before = MigrationContext.configure(conn, opts={"version_table": "identity_alembic_version"}).get_current_revision()
        command.upgrade(_config(conn), "head")
    return before, head()
