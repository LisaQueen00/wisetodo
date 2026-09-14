import runpy
import subprocess
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


@pytest.mark.parametrize("validation_fails", [False, True])
def test_macos_validates_final_dmg_without_intermediate_app(
    script, monkeypatch, tmp_path, validation_fails
):
    main = script["main"]
    namespace = main.__globals__
    dmg = tmp_path / "release/bundle/dmg/WiseTodo_0.1.0_aarch64.dmg"
    dmg.parent.mkdir(parents=True)
    dmg.touch()
    assert not (tmp_path / "release/bundle/macos/WiseTodo.app").exists()
    monkeypatch.setattr(sys, "argv", ["build_release.py"])
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("CARGO_TARGET_DIR", str(tmp_path))
    monkeypatch.setattr(namespace["shutil"], "which", lambda name: name)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)
    checked = []
    checksums = []

    def verify(path):
        checked.append(path)
        if validation_fails:
            raise ValueError("invalid final application")

    monkeypatch.setitem(namespace, "verify_dmg", verify)
    monkeypatch.setitem(namespace, "checksum", lambda *args: checksums.append(args))
    if validation_fails:
        with pytest.raises(ValueError, match="invalid final application"):
            main()
        assert not checksums
    else:
        main()
        assert checksums == [(dmg, "0.1.0")]
    assert checked == [dmg]
