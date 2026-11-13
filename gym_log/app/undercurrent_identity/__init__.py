"""Undercurrent identity: one account and one passkey for every Undercurrent app.

Source of truth: shared/undercurrent-identity/. Each app gets a copy via
`shared/undercurrent-identity/sync.sh <app>` (CI fails if a copy drifts).
Imports inside this package are relative, so the copy works whether the app
imports it as `undercurrent_identity` or `app.undercurrent_identity`.

Usage in an app:

    from .undercurrent_identity import Identity
    identity = Identity(app, app_name="gym_log")

    user = identity.current_user()     # User or None
    identity.has_access()              # signed in, not disabled, granted this app

Sign-up is invite-only and every app needs an explicit grant
(owner-approved on #50, 2026-11-13). The owner creates single-use invite
and recovery links on ATLAS with `flask identity invite|recover`.

Settings (environment variables):
  IDENTITY_DATABASE_URL   the shared `undercurrent_identity` database.
                          Unset: a SQLite file in the app's instance folder
                          (local dev and tests only).
  IDENTITY_RP_ID          WebAuthn relying-party id: the registrable domain
                          every app lives under (undercurrentlabs.dev), so one
                          passkey works on all of them. Default: localhost.
  IDENTITY_COOKIE_DOMAIN  e.g. .undercurrentlabs.dev, so signing in once
                          covers every app. Unset: host-only cookie (dev).
  IDENTITY_PUBLIC_URL     this app's public base URL, used in links the CLI
                          prints (https://gym.undercurrentlabs.dev).
"""
from __future__ import annotations

import os
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, current_app, g, jsonify, request

from .senders import LinkOnlySender, Sender
from .store import Store, User

__all__ = ["Identity", "User", "Sender", "LinkOnlySender", "SESSION_COOKIE"]

SESSION_COOKIE = "uc_session"
# How app ids read on the identity pages. Add new apps here.
APP_LABELS = {"gym_log": "Gym Log", "mindless_meals": "Mindless Meals", "capacity": "Capacity", "money_moves": "Money Moves"}


def app_label(app: str) -> str:
    return APP_LABELS.get(app, app.replace("_", " ").title())
EXTENSION_KEY = "undercurrent_identity"


class Identity:
    def __init__(self, app: Flask, app_name: str, sender: Sender | None = None):
        self.app_name = app_name
        cfg = app.config
        url = cfg.get("IDENTITY_DATABASE_URL") or os.environ.get("IDENTITY_DATABASE_URL")
        if not url:
            Path(app.instance_path).mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{Path(app.instance_path) / 'identity.db'}"
        self.store = Store(url)
        self.rp_id = cfg.get("IDENTITY_RP_ID") or os.environ.get("IDENTITY_RP_ID") or "localhost"
        self.rp_name = "Undercurrent"
        self.cookie_domain = cfg.get("IDENTITY_COOKIE_DOMAIN") or os.environ.get("IDENTITY_COOKIE_DOMAIN") or None
        self.public_url = (cfg.get("IDENTITY_PUBLIC_URL") or os.environ.get("IDENTITY_PUBLIC_URL") or "").rstrip("/")
        secure = cfg.get("IDENTITY_COOKIE_SECURE")
        self.cookie_secure = (self.rp_id != "localhost") if secure is None else bool(secure)
        self.sender: Sender = sender or LinkOnlySender()

        app.extensions[EXTENSION_KEY] = self
        if cfg.get("IDENTITY_AUTO_MIGRATE") or url.startswith("sqlite"):
            # Dev and tests: bring the SQLite file up to date on startup. On
            # Postgres, migrations run only through `flask identity migrate`.
            from . import migrate

            migrate.upgrade(self.store)

        from .cli import identity_cli
        from .views import make_blueprint

        app.register_blueprint(make_blueprint(self))
        app.cli.add_command(identity_cli)

        @app.context_processor
        def _identity_context():
            return {"uc_identity": self, "uc_user": self.current_user()}

    # --- the API apps use ---------------------------------------------------
    def current_user(self) -> User | None:
        if "uc_user" not in g:
            g.uc_user = self.store.user_for_session(request.cookies.get(SESSION_COOKIE, ""))
        return g.uc_user

    def has_access(self) -> bool:
        user = self.current_user()
        return bool(user and user.can_use(self.app_name))

    def require_access(self, view):
        """For JSON endpoints: 401 when signed out, 403 without a grant."""

        @wraps(view)
        def wrapped(*args, **kwargs):
            user = self.current_user()
            if user is None:
                return jsonify({"error": "Sign in to do that.", "sign_in": self.sign_in_url()}), 401
            if not user.can_use(self.app_name):
                return jsonify({"error": "Your account doesn't have access to this app."}), 403
            return view(*args, **kwargs)

        return wrapped

    def sign_in_url(self, next_path: str | None = None) -> str:
        from urllib.parse import quote

        nxt = next_path if next_path is not None else (request.full_path.rstrip("?") if request else "/")
        return f"/auth/sign-in?next={quote(nxt, safe='/')}"

    # --- helpers used by views ----------------------------------------------
    def allowed_origin(self, origin: str | None) -> bool:
        """WebAuthn origins (and the CSRF check on every POST): this domain
        and its subdomains, https only except on localhost."""
        if not origin:
            return False
        parsed = urlparse(origin)
        host = parsed.hostname or ""
        if self.rp_id == "localhost":
            return host in ("localhost", "127.0.0.1") and parsed.scheme in ("http", "https")
        return parsed.scheme == "https" and (host == self.rp_id or host.endswith("." + self.rp_id))

    def set_session_cookie(self, response, token: str) -> None:
        from .store import SESSION_LIFETIME

        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=int(SESSION_LIFETIME.total_seconds()),
            domain=self.cookie_domain,
            secure=self.cookie_secure,
            httponly=True,
            samesite="Lax",
            path="/",
        )

    def clear_session_cookie(self, response) -> None:
        response.delete_cookie(
            SESSION_COOKIE, domain=self.cookie_domain, path="/", secure=self.cookie_secure, httponly=True, samesite="Lax"
        )


def get_identity() -> Identity:
    return current_app.extensions[EXTENSION_KEY]
