"""Installable web app (Undercurrent web standard) and the page shell."""
import json
import subprocess
from pathlib import Path

SYNC = Path(__file__).resolve().parents[2] / "shared" / "undercurrent-web" / "sync.sh"


def test_manifest_is_installable(client):
    r = client.get("/manifest.webmanifest")
    assert r.headers["Content-Type"].startswith("application/manifest+json")
    m = json.loads(r.data)
    assert m["display"] == "standalone" and m["start_url"] == "/"
    assert {"192x192", "512x512"} <= {i["sizes"] for i in m["icons"]}
    assert any(i.get("purpose") == "maskable" for i in m["icons"])
    for i in m["icons"]:
        assert client.get(i["src"]).status_code == 200


def test_service_worker_and_health(client):
    assert client.get("/sw.js").headers["Content-Type"].startswith("text/javascript")
    assert client.get("/health").json == {"status": "ok"}


def test_home_page(client):
    html = client.get("/").get_data(as_text=True)
    for needle in ('rel="manifest"', 'rel="apple-touch-icon"', "apple-mobile-web-app-capable",
                   "Add Gym Log to your Home Screen", "js/gym-log.js", "js/logic.js", "js/icons.js"):
        assert needle in html
    assert client.get("/static/img/icons/apple-touch-icon.png").status_code == 200


def test_shared_snippet_copy_is_up_to_date():
    if not SYNC.exists():  # not in a full checkout (e.g. inside the image)
        return
    result = subprocess.run([str(SYNC), "--check", "gym_log"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
