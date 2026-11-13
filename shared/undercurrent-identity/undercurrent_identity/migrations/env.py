"""Alembic environment for the identity database. Run through
`flask identity migrate` (see migrate.py), which passes in the connection
and the metadata. The version table is `identity_alembic_version`, so this
history can never be confused with an app's own `alembic_version`."""
from alembic import context

config = context.config
connection = config.attributes["connection"]
context.configure(
    connection=connection,
    target_metadata=config.attributes["metadata"],
    version_table="identity_alembic_version",
    compare_type=True,
)
with context.begin_transaction():
    context.run_migrations()
