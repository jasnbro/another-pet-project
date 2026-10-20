# ATLAS server operations

Runbook for the self-hosted home server that runs these services. Moved here from the root README.


Services
--------
Jellyfin

Location
--------
~/services/jellyfin
~/services/mindless_meals

Deploying
---------
Mindless Meals deploys itself when a PR merges to main: see
deploy/README.md (setup, rollback, what to do when something fails).

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

