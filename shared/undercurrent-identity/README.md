# Undercurrent identity

One account and one passkey for every Undercurrent app (#50). Sign up is
**invite-only**, and each app needs its own **grant**. There's no email
service yet: invites and recovery are single-use links you create on ATLAS
and send yourself. Email (Resend) is #80.

| | |
|---|---|
| Sign in | Passkeys only (Face ID, Touch ID, PIN, security key). One passkey works on every `*.undercurrentlabs.dev` app |
| Session | Cookie `uc_session` on `.undercurrentlabs.dev`: Secure, HttpOnly, SameSite=Lax, 90 days. Only its SHA-256 hash is stored |
| Data | Its own database, `undercurrent_identity`, separate from every app's. Apps refer to people only by `users.id` |
| Pages | `/auth/sign-in`, `/auth/invite/<token>`, `/auth/recover/<token>`, `/auth/account` on every app that uses it |

## How apps use it

The package lives here and is **copied** into each app (each app's Docker
build only sees its own folder):

```
shared/undercurrent-identity/sync.sh gym_log            # after editing anything here
shared/undercurrent-identity/sync.sh --check gym_log    # CI does this
```

In the app:

```python
from .undercurrent_identity import Identity
identity = Identity(app, app_name="gym_log")

identity.current_user()     # User(id, email, display_name, apps) or None
identity.has_access()       # signed in, not disabled, and granted this app
@identity.require_access    # for JSON endpoints: 401 signed out, 403 no grant
```

Tests use `undercurrent_identity.testing.sign_in(client, identity, email)`,
plus `SoftPasskey`, a software passkey that makes real signatures.

## One-time setup on ATLAS

1. **Database.** From a checkout on ATLAS:
   `postgres/scripts/create_app_database.sh undercurrent_identity`.
   It prints a `DATABASE_URL` once; you'll use it as `IDENTITY_DATABASE_URL`.
   It connects as the Postgres container's own superuser. If it says
   `role "postgres" does not exist`, you have an older copy of the script;
   prefix the command with `POSTGRES_ADMIN_USER=<POSTGRES_USER from
   ~/services/postgres/.env>`.
2. **Each app's settings** get these lines: its Doppler `prd` config, or
   `~/services/<app>/.env` if it still uses one (`deploy/README.md` →
   *Settings*). The first three are the same for every app, so they can
   live once in a Doppler project `undercurrent-identity` and be referenced
   from each app.
   ```
   IDENTITY_DATABASE_URL=postgresql+psycopg2://undercurrent_identity_app:<password>@postgres:5432/undercurrent_identity
   IDENTITY_RP_ID=undercurrentlabs.dev
   IDENTITY_COOKIE_DOMAIN=.undercurrentlabs.dev
   IDENTITY_PUBLIC_URL=https://gym.undercurrentlabs.dev      # that app's own address
   ```
   Deploys refuse to run for an app that uses sign-in without these.
3. **Backups.** Add `undercurrent_identity` to the nightly job
   (`postgres/README.md` → *Backups*).
4. **Deploy** (merge, or Actions → Run workflow). The deploy backs up the
   identity database and runs `flask identity migrate` before switching.
5. **Your own account:**
   ```
   cd ~/services/gym_log
   docker compose exec gym_log flask --app app identity invite you@example.com --apps gym_log,mindless_meals
   ```
   Open the printed link on your iPad and create a passkey. To add your
   phone, open `/auth/account` there after signing in, or use a recovery link.

## Day to day (any app's container; they share the database)

| I want to… | Run `flask --app app identity …` |
|---|---|
| Invite someone | `invite friend@example.com --apps gym_log` (link works once, 7 days) |
| Give an existing account another app | `grant friend@example.com mindless_meals` |
| Take an app away (keeps their data) | `revoke friend@example.com gym_log` |
| Help someone who lost their passkey | `recover friend@example.com` (link works once, 24 hours) |
| Lost phone: end every session | `sign-out friend@example.com` |
| Block an account | `disable friend@example.com` (and `enable`) |
| See accounts | `users` |

Inside a container: `docker compose exec <app> flask --app app identity …`.

## Security notes

- Sign-up is invite-only, and links are single use, even if two devices
  race on one link (tested).
- Every `POST` must come from `https://undercurrentlabs.dev` or a
  subdomain. This covers the cross-subdomain case that SameSite=Lax
  doesn't.
- Raw session and link tokens are never stored. Passkeys are stored as
  public keys only.
- `next=` redirects only go to paths on the same site.
- Not yet: rate limiting (sign-in has no shared secret to guess) and
  email-code sign-in (#80).
