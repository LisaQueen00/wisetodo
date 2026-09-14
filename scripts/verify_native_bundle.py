"""Validate packaged icons and macOS signatures without installing or changing policy."""

import configparser
import plistlib
import subprocess
import tarfile
import tempfile
from pathlib import Path


def verify_macos(app: Path) -> None:
    contents = app / "Contents"
    with (contents / "Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    icon = info.get("CFBundleIconFile", "")
    if not icon or Path(icon).name != icon:
        raise ValueError("Missing or invalid macOS icon reference")
    icon_path = contents / "Resources" / (icon if icon.endswith(".icns") else icon + ".icns")
    if not icon_path.is_file() or icon_path.read_bytes()[:4] != b"icns":
        raise ValueError("Missing packaged ICNS icon")
    if not (contents / "_CodeSignature/CodeResources").is_file():
        raise ValueError("Missing application resource seal (linker signature is insufficient)")
    for binary in ("wisetodo", "wisetodo-sidecar"):
        subprocess.run(
            ["codesign", "--verify", "--strict", "--verbose=2", str(contents / "MacOS" / binary)],
            check=True,
        )
    subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)], check=True
    )


def verify_deb_tar(archive: tarfile.TarFile) -> None:
    members = {entry.name.removeprefix("./"): entry for entry in archive.getmembers()}
    desktops = [name for name in members if name.startswith("usr/share/applications/")
                and name.endswith(".desktop")]
    if len(desktops) != 1:
        raise ValueError("Expected one packaged desktop entry")
    stream = archive.extractfile(members[desktops[0]])
    if stream is None:
        raise ValueError("Missing desktop entry content")
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(stream.read().decode("utf-8"))
    icon = config.get("Desktop Entry", "Icon", fallback="")
    if not icon or Path(icon).name != icon:
        raise ValueError("Missing or invalid desktop icon name")
    icons = [entry for name, entry in members.items()
             if name.startswith("usr/share/icons/hicolor/")
             and name.endswith(f"/apps/{icon}.png") and entry.isfile()]
    if not icons:
        raise ValueError("Desktop icon has no matching hicolor PNG")
    for entry in icons:
        stream = archive.extractfile(entry)
        if stream is None or stream.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid packaged PNG icon")


def verify_deb(package: Path) -> None:
    # Read the archive without extracting paths or installing the package.
    with tempfile.TemporaryFile() as stream:
        subprocess.run(["dpkg-deb", "--fsys-tarfile", str(package)], stdout=stream, check=True)
        stream.seek(0)
        with tarfile.open(fileobj=stream) as archive:
            verify_deb_tar(archive)


def verify_dmg(package: Path) -> None:
    # Validate the shipped copy as well as the pre-DMG application bundle.
    with tempfile.TemporaryDirectory(prefix="wisetodo-dmg-check-") as directory:
        mount = Path(directory) / "volume"
        mount.mkdir()
        subprocess.run(
            ["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mount),
             str(package)], check=True,
        )
        try:
            verify_macos(mount / "WiseTodo.app")
        finally:
            subprocess.run(["hdiutil", "detach", str(mount)], check=True)
