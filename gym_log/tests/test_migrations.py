"""deploy/deploy.sh reads revisions from `alembic heads` / `alembic current`
with `grep -Eo '^[0-9a-f]{6,}'`. A hand-named revision like "0001" doesn't
match, and the deploy stops with "could not read migration heads" (it did,
on the first Gym Log deploy). Keep revision IDs Alembic-style hex."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SH = ROOT.parent / "deploy" / "deploy.sh"
DEPLOY_REGEX = re.compile(r"^[0-9a-f]{6,}", re.MULTILINE)  # same as deploy.sh


def test_deploy_script_still_uses_this_pattern():
    if not DEPLOY_SH.exists():  # not in a full checkout
        return
    assert "grep -Eo '^[0-9a-f]{6,}'" in DEPLOY_SH.read_text()


def test_alembic_heads_is_readable_by_deploy_script():
    out = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    heads = DEPLOY_REGEX.findall(out)
    assert len(heads) == 1, f"expected exactly one head readable by deploy.sh, got {out!r}"


def test_every_revision_id_is_hex():
    for path in (ROOT / "migrations" / "versions").glob("*.py"):
        rev = re.search(r'^revision = "([^"]+)"', path.read_text(), re.MULTILINE).group(1)
        assert re.fullmatch(r"[0-9a-f]{12}", rev), f"{path.name}: revision {rev!r} must be 12 hex chars"
