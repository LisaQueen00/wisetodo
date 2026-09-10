"""Validate release versions and checksum one existing native installer; never publish."""

import argparse
import hashlib
import json
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]


def release_version(root: Path) -> str:
    versions = [
        json.loads((root / "package.json").read_text(encoding="utf-8"))["version"],
        json.loads((root / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))[
            "version"
        ],
        tomllib.loads((root / "src-tauri/Cargo.toml").read_text(encoding="utf-8"))[
            "package"
        ]["version"],
        tomllib.loads((root / "backend/pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]["version"],
    ]
    lock = tomllib.loads((root / "src-tauri/Cargo.lock").read_text(encoding="utf-8"))
    versions.extend(
        row["version"] for row in lock["package"] if row["name"] == "wisetodo"
    )
    if len(versions) != 5 or len(set(versions)) != 1:
        raise ValueError("Application version mismatch (including Cargo.lock)")
    return versions[0]


def checksum(artifact: Path, version: str) -> Path:
    if artifact.is_symlink() or not artifact.is_file():
        raise ValueError("Expected a regular installer file")
    if (
        artifact.suffix not in {".exe", ".deb", ".dmg"}
        or f"_{version}_" not in artifact.name
    ):
        raise ValueError("Installer name must contain the matching application version")
    with artifact.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    output = artifact.with_name(artifact.name + ".sha256")
    if output.is_symlink():
        raise ValueError("Checksum output cannot be a symbolic link")
    output.write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args()
    version = release_version(ROOT)
    print(f"Application versions agree: {version}")
    if args.artifact is not None:
        print(checksum(args.artifact.absolute(), version))


if __name__ == "__main__":
    main()
