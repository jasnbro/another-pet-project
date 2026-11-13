"""The identity database: its own Postgres database (`undercurrent_identity`),
separate from every app's. Apps refer to people only by `users.id`.

Schema changes go through this package's Alembic migrations
(`flask identity migrate`), never create_all() on Postgres.

Secrets are never stored: session tokens and link tokens are kept as
SHA-256 hashes, passkeys as public keys.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    and_,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from .tokens import hash_token, new_id

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("email", String(320), nullable=False, unique=True),  # stored lowercased
    Column("display_name", String(120), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("disabled_at", DateTime(timezone=True)),
)

app_grants = Table(
    "app_grants",
    metadata,
    Column("user_id", String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("app", String(64), primary_key=True),
    Column("granted_at", DateTime(timezone=True), nullable=False),
)

passkeys = Table(
    "passkeys",
    metadata,
    Column("credential_id", String(1400), primary_key=True),  # base64url
    Column("user_id", String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("public_key", LargeBinary, nullable=False),
    Column("sign_count", Integer, nullable=False, default=0),
    Column("transports", String(200)),
    Column("name", String(120), nullable=False),
    Column("backed_up", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_used_at", DateTime(timezone=True)),
)

sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("user_agent", String(200)),
)

# Single-use invite and recovery links.
links = Table(
    "links",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("kind", String(16), nullable=False),  # invite | recovery
    Column("email", String(320), nullable=False),
    Column("apps", Text, nullable=False, default=""),  # comma-separated, invites only
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("used_at", DateTime(timezone=True)),
)

# WebAuthn challenges: single use, short-lived, server-side.
challenges = Table(
    "challenges",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("kind", String(16), nullable=False),  # register | authenticate
    Column("challenge", LargeBinary, nullable=False),
    Column("user_id", String(32)),
    Column("link_hash", String(64)),
    Column("display_name", String(120)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)

SESSION_LIFETIME = timedelta(days=90)
SESSION_TOUCH_EVERY = timedelta(hours=1)
CHALLENGE_LIFETIME = timedelta(minutes=5)


def now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    # SQLite returns naive datetimes; everything here is UTC.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@") or len(email) > 320:
        raise ValueError(f"not an email address: {email!r}")
    return email


@dataclass(frozen=True)
class User:
    id: str
    email: str
    display_name: str
    apps: frozenset[str] = field(default_factory=frozenset)
    disabled: bool = False

    def can_use(self, app: str) -> bool:
        return not self.disabled and app in self.apps


@dataclass(frozen=True)
class Link:
    kind: str
    email: str
    apps: tuple[str, ...]
    expires_at: datetime
    used: bool


class Store:
    def __init__(self, url: str):
        self.engine: Engine = create_engine(url, future=True, pool_pre_ping=True)

    # --- users ------------------------------------------------------------
    def _user_from_row(self, conn, row) -> User:
        apps = frozenset(conn.execute(select(app_grants.c.app).where(app_grants.c.user_id == row.id)).scalars())
        return User(row.id, row.email, row.display_name, apps, row.disabled_at is not None)

    def get_user(self, user_id: str) -> User | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(users).where(users.c.id == user_id)).first()
            return self._user_from_row(conn, row) if row else None

    def get_user_by_email(self, email: str) -> User | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(users).where(users.c.email == normalize_email(email))).first()
            return self._user_from_row(conn, row) if row else None

    def list_users(self) -> list[User]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(users).order_by(users.c.created_at)).all()
            return [self._user_from_row(conn, r) for r in rows]

    def grant(self, user_id: str, app: str, conn=None) -> None:
        def run(c):
            exists = c.execute(
                select(app_grants.c.app).where(and_(app_grants.c.user_id == user_id, app_grants.c.app == app))
            ).first()
            if not exists:
                c.execute(insert(app_grants).values(user_id=user_id, app=app, granted_at=now()))

        if conn is not None:
            return run(conn)
        with self.engine.begin() as c:
            run(c)

    def revoke(self, user_id: str, app: str) -> None:
        with self.engine.begin() as c:
            c.execute(delete(app_grants).where(and_(app_grants.c.user_id == user_id, app_grants.c.app == app)))

    def set_disabled(self, user_id: str, disabled: bool) -> None:
        with self.engine.begin() as c:
            c.execute(update(users).where(users.c.id == user_id).values(disabled_at=now() if disabled else None))
            if disabled:
                c.execute(delete(sessions).where(sessions.c.user_id == user_id))

    # --- links ------------------------------------------------------------
    def create_link(self, kind: str, email: str, apps: list[str] | tuple[str, ...] = (), days: int = 7) -> str:
        """Returns the raw token (shown once, never stored)."""
        assert kind in ("invite", "recovery")
        from .tokens import new_token

        token = new_token()
        with self.engine.begin() as c:
            c.execute(
                insert(links).values(
                    token_hash=hash_token(token),
                    kind=kind,
                    email=normalize_email(email),
                    apps=",".join(sorted(set(apps))),
                    created_at=now(),
                    expires_at=now() + timedelta(days=days),
                )
            )
        return token

    def get_link(self, token: str) -> Link | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(links).where(links.c.token_hash == hash_token(token))).first()
        if not row:
            return None
        apps = tuple(a for a in (row.apps or "").split(",") if a)
        return Link(row.kind, row.email, apps, _aware(row.expires_at), row.used_at is not None)

    def link_usable(self, token: str) -> Link | None:
        link = self.get_link(token)
        if link is None or link.used or link.expires_at <= now():
            return None
        return link

    # --- passkeys ---------------------------------------------------------
    def passkeys_for(self, user_id: str) -> list:
        with self.engine.connect() as conn:
            return conn.execute(
                select(passkeys).where(passkeys.c.user_id == user_id).order_by(passkeys.c.created_at)
            ).all()

    def get_passkey(self, credential_id: str):
        with self.engine.connect() as conn:
            return conn.execute(select(passkeys).where(passkeys.c.credential_id == credential_id)).first()

    def touch_passkey(self, credential_id: str, sign_count: int) -> None:
        with self.engine.begin() as c:
            c.execute(
                update(passkeys)
                .where(passkeys.c.credential_id == credential_id)
                .values(sign_count=sign_count, last_used_at=now())
            )

    def delete_passkey(self, user_id: str, credential_id: str) -> bool:
        """Refuses to delete a user's last passkey."""
        with self.engine.begin() as c:
            count = c.execute(select(func.count()).select_from(passkeys).where(passkeys.c.user_id == user_id)).scalar()
            if count <= 1:
                return False
            result = c.execute(
                delete(passkeys).where(and_(passkeys.c.user_id == user_id, passkeys.c.credential_id == credential_id))
            )
            return result.rowcount == 1

    # --- registration (invite, recovery, or adding a passkey) -------------
    def complete_registration(
        self,
        *,
        link_token_hash: str | None,
        user_id: str | None,
        display_name: str | None,
        credential_id: str,
        public_key: bytes,
        sign_count: int,
        transports: str | None,
        passkey_name: str,
        backed_up: bool,
    ) -> str:
        """Stores a new passkey and, for links, creates or finds the user and
        consumes the link. All in one transaction. Returns the user id.
        Raises ValueError if the link was used or expired meanwhile."""
        with self.engine.begin() as c:
            if link_token_hash:
                row = c.execute(select(links).where(links.c.token_hash == link_token_hash).with_for_update()).first()
                if row is None or row.used_at is not None or _aware(row.expires_at) <= now():
                    raise ValueError("This link has already been used or has expired.")
                existing = c.execute(select(users).where(users.c.email == row.email)).first()
                if row.kind == "invite":
                    if existing:
                        user_id = existing.id
                    else:
                        user_id = user_id or new_id()  # the WebAuthn user handle
                        c.execute(
                            insert(users).values(
                                id=user_id,
                                email=row.email,
                                display_name=(display_name or row.email.split("@")[0])[:120],
                                created_at=now(),
                            )
                        )
                    for app in (a for a in (row.apps or "").split(",") if a):
                        self.grant(user_id, app, conn=c)
                else:  # recovery
                    if not existing:
                        raise ValueError("No account for this recovery link.")
                    user_id = existing.id
                c.execute(update(links).where(links.c.token_hash == link_token_hash).values(used_at=now()))
            if not user_id:
                raise ValueError("No user for this registration.")
            c.execute(
                insert(passkeys).values(
                    credential_id=credential_id,
                    user_id=user_id,
                    public_key=public_key,
                    sign_count=sign_count,
                    transports=transports,
                    name=passkey_name[:120] or "Passkey",
                    backed_up=backed_up,
                    created_at=now(),
                )
            )
            return user_id

    # --- sessions ---------------------------------------------------------
    def create_session(self, user_id: str, user_agent: str | None = None) -> str:
        from .tokens import new_token

        token = new_token()
        t = now()
        with self.engine.begin() as c:
            c.execute(
                insert(sessions).values(
                    token_hash=hash_token(token),
                    user_id=user_id,
                    created_at=t,
                    expires_at=t + SESSION_LIFETIME,
                    last_seen_at=t,
                    user_agent=(user_agent or "")[:200] or None,
                )
            )
        return token

    def user_for_session(self, token: str) -> User | None:
        if not token:
            return None
        h = hash_token(token)
        t = now()
        with self.engine.connect() as conn:
            row = conn.execute(select(sessions).where(sessions.c.token_hash == h)).first()
            if row is None or _aware(row.expires_at) <= t:
                return None
            urow = conn.execute(select(users).where(users.c.id == row.user_id)).first()
            if urow is None or urow.disabled_at is not None:
                return None
            user = self._user_from_row(conn, urow)
        if t - _aware(row.last_seen_at) > SESSION_TOUCH_EVERY:
            with self.engine.begin() as c:
                c.execute(update(sessions).where(sessions.c.token_hash == h).values(last_seen_at=t))
        return user

    def end_session(self, token: str) -> None:
        with self.engine.begin() as c:
            c.execute(delete(sessions).where(sessions.c.token_hash == hash_token(token)))

    def end_all_sessions(self, user_id: str) -> int:
        with self.engine.begin() as c:
            return c.execute(delete(sessions).where(sessions.c.user_id == user_id)).rowcount

    # --- challenges ---------------------------------------------------------
    def save_challenge(self, kind: str, challenge: bytes, **values) -> str:
        cid = new_id()
        t = now()
        with self.engine.begin() as c:
            c.execute(delete(challenges).where(challenges.c.expires_at < t))
            c.execute(
                insert(challenges).values(
                    id=cid, kind=kind, challenge=challenge, created_at=t, expires_at=t + CHALLENGE_LIFETIME, **values
                )
            )
        return cid

    def pop_challenge(self, cid: str, kind: str):
        """Single use: returns the row and deletes it, or None if unknown/expired."""
        with self.engine.begin() as c:
            row = c.execute(select(challenges).where(and_(challenges.c.id == cid, challenges.c.kind == kind))).first()
            if row is None:
                return None
            c.execute(delete(challenges).where(challenges.c.id == cid))
        if _aware(row.expires_at) <= now():
            return None
        return row
