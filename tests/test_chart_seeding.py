"""The chart's IGM seeding script, exercised as a script.

The init container copies bundled IGMs onto the data volume. Its first
version was all-or-nothing -- "if the directory exists, do nothing" -- so a
release that added new IGMs could never deliver them to a realm that had
already been seeded, and enabling one in config did nothing because the
loader never saw it on disk. These tests run the *rendered* script the way
the pod does.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest
import yaml

pytestmark = pytest.mark.skipif(
    shutil.which("helm") is None, reason="helm is not installed"
)


def _seed_script() -> str:
    rendered = subprocess.run(
        ["helm", "template", "pylord", "deploy/helm/pylord",
         "-f", "deploy/values/prod.yaml"],
        capture_output=True, text=True, check=True,
    ).stdout
    docs = [d for d in yaml.safe_load_all(rendered) if d]
    dep = next(d for d in docs if d["kind"] == "Deployment")
    init = next(
        c for c in dep["spec"]["template"]["spec"]["initContainers"]
        if c["name"] == "seed-igms"
    )
    return init["args"][0]


def _run(tmp_path, image_igms, volume_igms):
    """Run the script against fake /app/igms and /data layouts."""
    app = tmp_path / "app" / "igms"
    for name in image_igms:
        (app / name).mkdir(parents=True)
        (app / name / "igm.py").write_text("# bundled\n")
    data = tmp_path / "data"
    data.mkdir()
    for name in volume_igms:
        (data / "igms" / name).mkdir(parents=True)
        (data / "igms" / name / "igm.py").write_text("# sysop's copy\n")

    script = _seed_script().replace("/app/igms", str(app)).replace("/data", str(data))
    subprocess.run(["sh", "-c", script], check=True, capture_output=True)
    return sorted(p.name for p in (data / "igms").iterdir() if p.is_dir())


def test_seeds_everything_onto_a_fresh_volume(tmp_path):
    assert _run(tmp_path, ["baraks_house", "apothecary"], []) == [
        "apothecary", "baraks_house"
    ]


def test_delivers_igms_added_by_a_later_release(tmp_path):
    """The bug: a volume seeded with the starter six never received the
    wave-2 IGMs, so they could not be enabled at all."""
    assert _run(tmp_path, ["baraks_house", "apothecary"], ["baraks_house"]) == [
        "apothecary", "baraks_house"
    ]


def test_never_overwrites_a_sysops_edits(tmp_path):
    app = tmp_path / "app" / "igms" / "baraks_house"
    app.mkdir(parents=True)
    (app / "igm.py").write_text("# bundled\n")
    data = tmp_path / "data" / "igms" / "baraks_house"
    data.mkdir(parents=True)
    (data / "igm.py").write_text("# EDITED BY THE SYSOP\n")

    script = _seed_script().replace(
        "/app/igms", str(tmp_path / "app" / "igms")
    ).replace("/data", str(tmp_path / "data"))
    subprocess.run(["sh", "-c", script], check=True, capture_output=True)

    assert (data / "igm.py").read_text() == "# EDITED BY THE SYSOP\n"


def test_a_deleted_igm_stays_deleted(tmp_path):
    """Seeding twice must not resurrect something removed on purpose."""
    app = tmp_path / "app" / "igms"
    for name in ["baraks_house", "the_latrine"]:
        (app / name).mkdir(parents=True)
        (app / name / "igm.py").write_text("# bundled\n")
    data = tmp_path / "data"
    (data / "igms").mkdir(parents=True)

    script = _seed_script().replace("/app/igms", str(app)).replace("/data", str(data))
    subprocess.run(["sh", "-c", script], check=True, capture_output=True)
    shutil.rmtree(data / "igms" / "the_latrine")  # the sysop bins it
    subprocess.run(["sh", "-c", script], check=True, capture_output=True)

    assert sorted(p.name for p in (data / "igms").iterdir() if p.is_dir()) == [
        "baraks_house"
    ]
