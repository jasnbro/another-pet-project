"""Installable web app + "Add to Home Screen" shortcut (issue #34)."""
import json
import pathlib
import subprocess

APP_DIR = pathlib.Path(__file__).resolve().parents[1]
SYNC = APP_DIR.parents[1] / "shared" / "undercurrent-web" / "sync.sh"


def test_manifest_is_installable(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/manifest+json")
    manifest = json.loads(response.data)
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    sizes = {i["sizes"] for i in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert any(i.get("purpose") == "maskable" for i in manifest["icons"])
    for icon in manifest["icons"]:
        assert client.get(icon["src"]).status_code == 200, icon["src"]


def test_service_worker_served_from_root(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/javascript")
    assert b"addEventListener" in response.data


def test_home_page_has_install_tags_and_shortcut(client):
    html = client.get("/").get_data(as_text=True)
    assert 'rel="manifest"' in html
    assert 'rel="apple-touch-icon"' in html
    assert 'id="uc-install"' in html
    assert 'id="uc-install-steps"' in html
    assert "install-shortcut.js" in html
    assert "Add Mindless Meals to your Home Screen" in html


def test_shared_snippet_copy_is_up_to_date():
    # Only meaningful in a full repo checkout (not inside the app container).
    if not SYNC.exists():
        return
    result = subprocess.run([str(SYNC), "--check", "mindless_meals"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
