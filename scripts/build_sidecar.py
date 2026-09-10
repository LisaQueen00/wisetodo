"""Build a native frozen backend; run with the project's virtual environment."""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    host = subprocess.check_output(
        ["rustc", "--print", "host-tuple"], text=True
    ).strip()
    architectures = {
        "AMD64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "aarch64": "aarch64",
    }
    if host.split("-")[0] != architectures.get(platform.machine()):
        raise SystemExit("Python and Rust must use the same native architecture")
    work = ROOT / "backend" / "build" / "sidecar"
    output = ROOT / "backend" / "dist"
    work.mkdir(parents=True, exist_ok=True)
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name",
        "wisetodo-sidecar",
        "--distpath",
        str(output),
        "--workpath",
        str(work),
        "--specpath",
        str(work),
        "--paths",
        str(ROOT / "backend"),
        "--add-data",
        f"{ROOT / 'backend' / 'alembic.ini'}:.",
        "--add-data",
        f"{ROOT / 'backend' / 'alembic'}:alembic",
    ]
    for package in ("wisetodo", "langgraph", "keyring"):
        args.extend(["--collect-all", package])
    for distribution in ("langgraph", "langchain-core", "openai", "mcp", "keyring"):
        args.extend(["--recursive-copy-metadata", distribution])
    args.append(str(ROOT / "backend" / "wisetodo" / "main.py"))
    subprocess.run(args, cwd=ROOT, check=True)
    extension = ".exe" if sys.platform == "win32" else ""
    binary = output / f"wisetodo-sidecar{extension}"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "smoke_sidecar.py"), str(binary)],
        check=True,
    )
    destination = (
        ROOT / "src-tauri" / "binaries" / f"wisetodo-sidecar-{host}{extension}"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, destination)
    print(f"Prepared {destination.name}")


if __name__ == "__main__":
    main()
