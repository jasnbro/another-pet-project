"""catalog.csv is generated and committed with its frames: both must stay in
step with catalog/build_catalog.py and the vendored sources."""
import csv
import importlib.util
from pathlib import Path

from .conftest import DATA

GYM_LOG = DATA.parent
FRAMES = GYM_LOG / "frames"
BUILDER = GYM_LOG / "catalog" / "build_catalog.py"


def _rows(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_catalog_csv_is_up_to_date(tmp_path):
    """If this fails, run `uv run python catalog/build_catalog.py` and commit
    data/catalog.csv. Never hand-edit the CSV."""
    spec = importlib.util.spec_from_file_location("build_catalog", BUILDER)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.main(tmp_path / "catalog.csv")
    assert (tmp_path / "catalog.csv").read_text(encoding="utf-8") == (DATA / "catalog.csv").read_text(encoding="utf-8")


def test_every_frame_in_the_catalog_exists():
    missing = [
        p for row in _rows(DATA / "catalog.csv") for p in row["frame_paths"].split("|") if p and not (FRAMES / p).is_file()
    ]
    assert missing == []


def test_frame_license_files_ship_with_the_frames():
    assert (FRAMES / "LICENSE-ASSETS").is_file()
    assert (FRAMES / "ATTRIBUTION.md").is_file()


def test_dockerfile_copies_frames_before_the_code():
    """The frames' layer must come before the code COPYs, or it rebuilds on
    every deploy and each kept image stores its own 33 MB (frames/README.md)."""
    copies = [line.split()[1] for line in (GYM_LOG / "Dockerfile").read_text().splitlines() if line.startswith("COPY ") and "--from" not in line]
    assert "frames/" in copies
    assert copies.index("frames/") < min(copies.index(p) for p in ("app/", "data/", "migrations/"))
