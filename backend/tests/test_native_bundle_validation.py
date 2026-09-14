import io
import json
import plistlib
import runpy
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = runpy.run_path(str(ROOT / "scripts/verify_native_bundle.py"))


def test_icon_and_signing_configuration():
    config = json.loads((ROOT / "src-tauri/tauri.conf.json").read_text())
    icons = config["bundle"]["icon"]
    assert {Path(icon).suffix for icon in icons} == {".png", ".icns", ".ico"}
    assert all((ROOT / "src-tauri" / icon).is_file() for icon in icons)
    release = json.loads((ROOT / "src-tauri/tauri.bundle.conf.json").read_text())
    assert release["bundle"]["macOS"]["signingIdentity"] == "-"


@pytest.mark.parametrize("missing", [None, "icon", "seal"])
def test_macos_checks_resources_before_signature(tmp_path, monkeypatch, missing):
    contents = tmp_path / "Contents"
    (contents / "Resources").mkdir(parents=True)
    (contents / "_CodeSignature").mkdir()
    (contents / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIconFile": "icon.icns"}))
    if missing != "icon":
        (contents / "Resources/icon.icns").write_bytes(b"icnsfixture")
    if missing != "seal":
        (contents / "_CodeSignature/CodeResources").touch()
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: calls.append((args, kw)))
    if missing:
        with pytest.raises(ValueError):
            MODULE["verify_macos"](tmp_path)
        assert not calls
    else:
        MODULE["verify_macos"](tmp_path)
        assert len(calls) == 3
        assert "--deep" in calls[-1][0]
        assert all(kw["check"] for _, kw in calls)


@pytest.mark.parametrize("icon", ["wisetodo", "missing", ""])
def test_deb_icon_must_resolve_to_packaged_png(icon):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data in {
            "./usr/share/applications/WiseTodo.desktop":
                f"[Desktop Entry]\nName=WiseTodo\nIcon={icon}\n".encode(),
            "./usr/share/icons/hicolor/128x128/apps/wisetodo.png": b"\x89PNG\r\n\x1a\n",
        }.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
    buffer.seek(0)
    with tarfile.open(fileobj=buffer) as archive:
        if icon == "wisetodo":
            MODULE["verify_deb_tar"](archive)
        else:
            with pytest.raises(ValueError):
                MODULE["verify_deb_tar"](archive)


def test_signature_failure_is_fatal(tmp_path, monkeypatch):
    contents = tmp_path / "Contents"
    (contents / "Resources").mkdir(parents=True)
    (contents / "_CodeSignature").mkdir()
    (contents / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIconFile": "icon"}))
    (contents / "Resources/icon.icns").write_bytes(b"icnsfixture")
    (contents / "_CodeSignature/CodeResources").touch()

    def fail(args, **kwargs):
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        MODULE["verify_macos"](tmp_path)


@pytest.mark.parametrize("fails", [False, True])
def test_dmg_readonly_mount_is_detached_even_when_validation_fails(monkeypatch, fails):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: calls.append(args))

    def verify(app):
        assert app.name == "WiseTodo.app"
        if fails:
            raise ValueError("bad signature")

    function = MODULE["verify_dmg"]
    monkeypatch.setitem(function.__globals__, "verify_macos", verify)
    if fails:
        with pytest.raises(ValueError, match="bad signature"):
            function(Path("fixture.dmg"))
    else:
        function(Path("fixture.dmg"))
    assert calls[0][:4] == ["hdiutil", "attach", "-readonly", "-nobrowse"]
    assert calls[-1][:2] == ["hdiutil", "detach"]
