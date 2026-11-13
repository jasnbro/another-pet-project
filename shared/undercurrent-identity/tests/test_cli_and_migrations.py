from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext

from undercurrent_identity import migrate
from undercurrent_identity.store import metadata


def run(app, *args):
    return app.test_cli_runner().invoke(args=["identity", *args])


def test_invite_prints_a_single_use_link(app, identity):
    app.config["IDENTITY_PUBLIC_URL"] = ""
    identity.public_url = "https://gym.undercurrentlabs.dev"
    r = run(app, "invite", "Friend@Example.com", "--apps", "gym_log,mindless_meals")
    assert r.exit_code == 0, r.output
    assert "Not emailed" in r.output
    url = [line.strip() for line in r.output.splitlines() if "/auth/invite/" in line][0]
    assert url.startswith("https://gym.undercurrentlabs.dev/auth/invite/")
    link = identity.store.link_usable(url.rsplit("/", 1)[1])
    assert link.email == "friend@example.com" and set(link.apps) == {"gym_log", "mindless_meals"}


def test_admin_commands(app, identity):
    from undercurrent_identity.testing import create_user

    create_user(identity, "a@example.com", ["gym_log"])
    assert "a@example.com" in run(app, "users").output
    assert run(app, "grant", "a@example.com", "mindless_meals").exit_code == 0
    assert identity.store.get_user_by_email("a@example.com").apps == {"gym_log", "mindless_meals"}
    assert run(app, "revoke", "a@example.com", "gym_log").exit_code == 0
    assert run(app, "disable", "a@example.com").exit_code == 0
    assert identity.store.get_user_by_email("a@example.com").disabled
    assert run(app, "enable", "a@example.com").exit_code == 0
    assert "Recovery link" in run(app, "recover", "a@example.com").output
    r = run(app, "recover", "nobody@example.com")
    assert r.exit_code != 0 and "No account" in r.output


def test_migrate_is_idempotent_and_matches_the_tables(app, identity):
    r = run(app, "migrate")
    assert r.exit_code == 0 and r.output.strip().endswith(migrate.head())
    assert run(app, "current").output.strip() == migrate.head()
    with identity.store.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), metadata)
    assert [d for d in diff if d[0] != "remove_table" or d[1].name != "identity_alembic_version"] == []
