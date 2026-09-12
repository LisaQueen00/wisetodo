import runpy
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def script(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return runpy.run_path(str(ROOT / "scripts/build_release.py"))


@pytest.mark.parametrize(
    ("platform", "bundle"),
    [
        ("win32", "nsis"),
        ("darwin", "dmg"),
        ("linux", "deb"),
    ],
)
def test_native_bundle(script, platform, bundle):
    assert script["native_bundle"](platform) == bundle


def test_unsupported_host(script):
    with pytest.raises(ValueError):
        script["native_bundle"]("unknown")


def test_windows_archive_only_includes_allowlisted_files(script, tmp_path):
    for name in ("wisetodo.exe", "wisetodo-sidecar.exe", "personal.db", "model-settings.json"):
        (tmp_path / name).write_bytes(b"fixture")
    output = script["windows_archive"](tmp_path, "0.1.0", "x86_64-pc-windows-msvc")
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {"wisetodo.exe", "wisetodo-sidecar.exe", "START-HERE.md"}
    assert output.with_name(output.name + ".sha256").is_file()


def test_windows_archive_requires_sidecar(script, tmp_path):
    (tmp_path / "wisetodo.exe").touch()
    with pytest.raises(ValueError):
        script["windows_archive"](tmp_path, "0.1.0", "x86_64-pc-windows-msvc")


def test_builder_help_is_non_mutating(script, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build_release.py", "--help"])
    with pytest.raises(SystemExit) as result:
        script["main"]()
    assert result.value.code == 0
