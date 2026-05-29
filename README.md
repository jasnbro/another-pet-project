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

Notes
-----
- Use the jasmine user for day-to-day administration.
- Avoid working as root unless performing OS-level maintenance.
- Jellyfin uses HTTP by default.
- Safari may attempt HTTPS and show SSL errors.
- Tailscale connectivity must be active on the client device.
- All self-hosted services should live under ~/services.
- Each service should contain its own compose.yml and persistent data.
