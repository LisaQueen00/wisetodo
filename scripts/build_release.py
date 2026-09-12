"""Build unsigned native test packages; never install, publish or include user data."""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from prepare_release import checksum, release_version

ROOT = Path(__file__).resolve().parents[1]


def native_bundle(platform: str) -> str:
    bundles = {"win32": "nsis", "darwin": "dmg", "linux": "deb"}
    if platform not in bundles:
        raise ValueError("Supported native hosts: Windows, macOS, Linux")
    return bundles[platform]


def windows_archive(release: Path, version: str, host: str) -> Path:
    files = [release / "wisetodo.exe", release / "wisetodo-sidecar.exe"]
    if any(not file.is_file() or file.is_symlink() for file in files):
        raise ValueError("Missing regular Windows application/Sidecar file")
    folder = release / "bundle" / "direct-run"
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / f"WiseTodo_{version}_{host}-direct-run.zip"
    if archive.is_symlink():
        raise ValueError("Archive cannot be a symbolic link")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for file in files:
            output.write(file, file.name)
        output.write(ROOT / "docs" / "getting-started.md", "START-HERE.md")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    destination = archive.with_name(archive.name + ".sha256")
    if destination.is_symlink():
        raise ValueError("Checksum cannot be a symbolic link")
    destination.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cargo-offline",
        action="store_true",
        help="Use cached Cargo dependencies; bundler may still require networking",
    )
    args = parser.parse_args()
    bundle = native_bundle(sys.platform)
    pnpm = shutil.which("pnpm.cmd" if sys.platform == "win32" else "pnpm")
    if not pnpm or not shutil.which("cargo") or not shutil.which("rustc"):
        raise SystemExit(
            "Install pnpm and Rust, then reopen the terminal (see docs/building.md)"
        )
    version = release_version(ROOT)
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "src-tauri" / "target"))
    if not target.is_absolute():
        target = ROOT / target
    target = target.resolve()
    environment = {**os.environ, "CARGO_TARGET_DIR": str(target)}

    def run(command: list[str]) -> None:
        subprocess.run(command, cwd=ROOT, env=environment, check=True)

    run([sys.executable, str(ROOT / "scripts/build_sidecar.py")])
    run(
        [
            pnpm,
            "exec",
            "tauri",
            "build",
            "--config",
            "src-tauri/tauri.bundle.conf.json",
            "--bundles",
            bundle,
            "--",
            "--locked",
            *(["--offline"] if args.cargo_offline else []),
        ]
    )
    release = target / "release"
    extension = ".exe" if sys.platform == "win32" else ""
    run(
        [
            sys.executable,
            str(ROOT / "scripts/accept_release.py"),
            str(release / f"wisetodo-sidecar{extension}"),
        ]
    )
    suffix = {"nsis": ".exe", "deb": ".deb", "dmg": ".dmg"}[bundle]
    artifacts = list((release / "bundle" / bundle).glob(f"*_{version}_*{suffix}"))
    if not artifacts:
        raise RuntimeError("No matching installer was produced")
    for artifact in artifacts:
        print(checksum(artifact, version))
    shutil.copy2(ROOT / "docs/getting-started.md", release / "bundle/START-HERE.md")
    if sys.platform == "win32":
        host = subprocess.check_output(
            ["rustc", "--print", "host-tuple"], text=True
        ).strip()
        print(windows_archive(release, version, host))
    print(f"Native {bundle} build complete: {release / 'bundle'}")


if __name__ == "__main__":
    main()
