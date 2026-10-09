# Developer Checklist for AI Agents

Read this before developing or testing in this repo (Claude, Codex, or
any other coding agent). Each point below cost real debugging time to
learn — skipping the check doesn't skip the risk. **Add a new point**
whenever you hit something here that would have saved you time or
caught a mistake before it shipped. Keep entries terse: one tight
paragraph, concrete and specific, not general advice.

- **ORM auto-schema-creation vs. a real migration tool: verify they
  can't collide, against the *actual* target database's history, not
  a fresh one.** `db.create_all()` (or equivalent) silently no-ops on
  tables that already exist but will happily create *new* ones
  out-of-band — then a migration tool replaying "from empty" fails the
  instant it hits a `CREATE TABLE` for something already there. Worse:
  simulating this by running "old code, then new code" against a
  *fresh* throwaway database isn't enough either, if "new code" is
  what you use to create the "old" layer — any constraint/model change
  already in that code gets baked into step one, masking exactly the
  gap you're trying to find. Use the actual pre-change code to build
  each historical layer. (mindless_meals: `db.create_all()` is now
  gated to SQLite only; see `mindless_meals/docs/database.md`'s Atlas
  deployment section for the one-time adoption this caused.)

- **After hand-fixing schema drift, verify with the migration tool's
  own diff, not your own reasoning.** `alembic revision --autogenerate`
  (or equivalent) against a database you believe now matches your
  models is a cheap, authoritative check — an empty generated migration
  means zero drift. Trust it over "I think I got everything."

- **Postgres admin/provisioning scripts: match the real role topology,
  not a generic admin role.** `REASSIGN OWNED BY` unconditionally fails
  when the source role is the cluster's bootstrap superuser (fixed OID
  10) — which is exactly what `POSTGRES_USER` is on the official
  postgres image, and exactly who owns every app's database here
  today. A script "verified" against some other admin role proves
  nothing about this server.

- **Never check out an unrelated branch in a live bind-mounted
  production directory.** If `compose.yml` bind-mounts the app
  directory into a running container, switching branches there swaps
  live code out from under it. Clone into an isolated scratch
  directory for anything that isn't the deploy itself.

- **Never write test data into the real production database.** Prefer
  read-only checks (GET endpoints, redacted env/config reads) against
  live prod. For anything that writes, use an isolated throwaway
  container + database — never create/delete real rows just to confirm
  a feature works.

- **Redact credentials even in your own output.** When inspecting a
  live container's env/config (e.g. `DATABASE_URL`), strip embedded
  passwords before printing them, even to yourself.
