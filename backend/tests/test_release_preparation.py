import hashlib
import runpy
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = runpy.run_path(str(ROOT / "scripts/prepare_release.py"))
FILES = [
    "package.json",
    "src-tauri/tauri.conf.json",
    "src-tauri/Cargo.toml",
    "backend/pyproject.toml",
    "src-tauri/Cargo.lock",
]


def test_repository_versions_agree():
    assert SCRIPT["release_version"](ROOT) == "0.1.0"


@pytest.mark.parametrize("changed", FILES)
def test_version_drift_is_rejected(tmp_path, changed):
    for name in FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    target = tmp_path / changed
    target.write_text(
        target.read_text(encoding="utf-8").replace("0.1.0", "0.1.1"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="mismatch"):
        SCRIPT["release_version"](tmp_path)


@pytest.mark.parametrize("extension", ["exe", "deb", "dmg"])
def test_checksum_matches_bytes_and_preserves_artifact(tmp_path, extension):
    artifact = tmp_path / f"WiseTodo_0.1.0_x64.{extension}"
    data = b"test installer bytes"
    artifact.write_bytes(data)
    result = SCRIPT["checksum"](artifact, "0.1.0")
    assert result.read_text() == f"{hashlib.sha256(data).hexdigest()}  {artifact.name}\n"
    assert artifact.read_bytes() == data


@pytest.mark.parametrize("name", ["WiseTodo_0.2.0_x64.exe", "model-settings.json"])
def test_wrong_version_or_noninstaller_is_rejected(tmp_path, name):
    artifact = tmp_path / name
    artifact.touch()
    with pytest.raises(ValueError):
        SCRIPT["checksum"](artifact, "0.1.0")
    assert not artifact.with_name(name + ".sha256").exists()
