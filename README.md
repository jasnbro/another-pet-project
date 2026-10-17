A repo for random projects that I think of as I fall back in love with data.

Atlas

Services
--------
Jellyfin

Location
--------
~/services/jellyfin
~/services/mindless_meals

Start
-----
cd ~/services/<service_name>
docker compose up -d

Stop
----
cd ~/services/<service_name>
docker compose down

Logs
----
cd ~/services/<service_name>
docker compose logs -f

Access
------
LAN:
http://<atlas-lan-ip>:8096

Tailscale:
http://<atlas-tailscale-ip>:8096

Infrastructure Services
-----------------------
postgres
- Shared database server
- One database per application
- Internal only (atlas-data network) — never exposed on a host port in
  production; see postgres/compose.dev.yml for local-dev-only access
- Setup, schema, migrations, backups: see mindless_meals/docs/database.md
  (written from the mindless_meals app's perspective, but the postgres
  service setup / backup scripts there apply to any app sharing this
  server)

Application Services
--------------------
jellyfin
mindless_meals
future applications

Notes
-----
- Use the jasmine user for day-to-day administration.
- Avoid working as root unless performing OS-level maintenance.
- Jellyfin uses HTTP by default.
- Safari may attempt HTTPS and show SSL errors.
- Tailscale connectivity must be active on the client device.
- All self-hosted services should live under ~/services.
- Each service should contain its own compose.yml and persistent data.

AI-authored work
----------------
- Claude and ChatGPT post through the owner's GitHub account, so the
  GitHub author is always jasnbro. Mark AI-written work explicitly.
- Issues and PRs: add the `author:claude` or `author:chatgpt` label.
- Issue bodies, PR descriptions and comments: end with a footer naming
  the model, e.g. `*Authored by Claude (Anthropic, Claude Opus 5.5)
  via the user's GitHub account.*`
- Commits: include a `Co-Authored-By:` trailer for the agent.
