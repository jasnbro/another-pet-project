"""`flask identity ...`: the owner's tools, run on ATLAS inside any app's
container, e.g.

    cd ~/services/gym_log
    docker compose exec gym_log flask --app app identity invite friend@example.com --apps gym_log

Every app shares the one identity database, so it doesn't matter which
app's container you use, except that printed links point at that app's
IDENTITY_PUBLIC_URL.
"""
import click
from flask import current_app
from flask.cli import with_appcontext

from . import migrate as migrations
from .store import normalize_email

INVITE_DAYS = 7
RECOVERY_DAYS = 1


def _identity():
    return current_app.extensions["undercurrent_identity"]


def _link(path: str) -> str:
    identity = _identity()
    base = identity.public_url or "http://localhost:5000"
    return f"{base}{path}"


def _user_or_exit(email):
    user = _identity().store.get_user_by_email(email)
    if user is None:
        raise click.ClickException(f"No account for {normalize_email(email)}.")
    return user


@click.group("identity")
def identity_cli():
    """Undercurrent accounts: invites, recovery, access."""


@identity_cli.command("migrate")
@with_appcontext
def migrate_cmd():
    """Bring the identity database's schema up to date."""
    before, after = migrations.upgrade(_identity().store)
    click.echo(f"identity database: {before or 'empty'} -> {after}")


@identity_cli.command("current")
@with_appcontext
def current_cmd():
    """Print the identity database's migration revision (empty if none)."""
    click.echo(migrations.current(_identity().store) or "")


@identity_cli.command("invite")
@click.argument("email")
@click.option("--apps", required=True, help="Comma-separated apps to grant, e.g. gym_log,mindless_meals")
@with_appcontext
def invite_cmd(email, apps):
    """Create a single-use invite link (expires in 7 days)."""
    identity = _identity()
    email = normalize_email(email)
    app_list = [a.strip() for a in apps.split(",") if a.strip()]
    token = identity.store.create_link("invite", email, app_list, days=INVITE_DAYS)
    url = _link(f"/auth/invite/{token}")
    existing = identity.store.get_user_by_email(email)
    note = " (existing account: adds access and a passkey)" if existing else ""
    sent = identity.sender.send(
        email,
        "You're invited to Undercurrent",
        f"Set up your passkey to start using {', '.join(app_list)}:\n\n{url}\n\n"
        f"This link works once and expires in {INVITE_DAYS} days.",
    )
    click.echo(f"Invite for {email} -> {', '.join(app_list)}{note}")
    click.echo("Sent by email." if sent else "Not emailed (no email service yet). Send this link yourself:")
    click.echo(f"  {url}")
    click.echo(f"It works once and expires in {INVITE_DAYS} days.")


@identity_cli.command("recover")
@click.argument("email")
@with_appcontext
def recover_cmd(email):
    """Create a single-use link to add a new passkey (expires in 24 hours)."""
    identity = _identity()
    user = _user_or_exit(email)
    token = identity.store.create_link("recovery", user.email, days=RECOVERY_DAYS)
    url = _link(f"/auth/recover/{token}")
    sent = identity.sender.send(
        user.email,
        "Recover your Undercurrent account",
        f"Use this link to add a new passkey:\n\n{url}\n\nIt works once and expires in 24 hours.",
    )
    click.echo(f"Recovery link for {user.email}")
    click.echo("Sent by email." if sent else "Not emailed (no email service yet). Send this link yourself:")
    click.echo(f"  {url}")
    click.echo("It works once and expires in 24 hours. Existing passkeys keep working.")


@identity_cli.command("users")
@with_appcontext
def users_cmd():
    """List accounts and the apps each can use."""
    store = _identity().store
    for u in store.list_users():
        state = " (disabled)" if u.disabled else ""
        n = len(store.passkeys_for(u.id))
        click.echo(f"{u.email}  {u.display_name!r}  apps={','.join(sorted(u.apps)) or '-'}  passkeys={n}  id={u.id}{state}")


@identity_cli.command("grant")
@click.argument("email")
@click.argument("app")
@with_appcontext
def grant_cmd(email, app):
    """Give an existing account access to an app."""
    user = _user_or_exit(email)
    _identity().store.grant(user.id, app)
    click.echo(f"{user.email} can now use {app}.")


@identity_cli.command("revoke")
@click.argument("email")
@click.argument("app")
@with_appcontext
def revoke_cmd(email, app):
    """Remove an account's access to an app (its data is kept)."""
    user = _user_or_exit(email)
    _identity().store.revoke(user.id, app)
    click.echo(f"{user.email} can no longer use {app}.")


@identity_cli.command("disable")
@click.argument("email")
@with_appcontext
def disable_cmd(email):
    """Block an account everywhere and sign it out."""
    user = _user_or_exit(email)
    _identity().store.set_disabled(user.id, True)
    click.echo(f"{user.email} is disabled and signed out everywhere.")


@identity_cli.command("enable")
@click.argument("email")
@with_appcontext
def enable_cmd(email):
    """Re-enable a disabled account."""
    user = _user_or_exit(email)
    _identity().store.set_disabled(user.id, False)
    click.echo(f"{user.email} is enabled.")


@identity_cli.command("sign-out")
@click.argument("email")
@with_appcontext
def sign_out_cmd(email):
    """End every session for an account (e.g. a lost phone)."""
    user = _user_or_exit(email)
    n = _identity().store.end_all_sessions(user.id)
    click.echo(f"Ended {n} session(s) for {user.email}.")
