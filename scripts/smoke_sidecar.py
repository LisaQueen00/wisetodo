"""Exercise frozen startup/migrations/IPC/reopen without credentials or networking."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    binary = Path(sys.argv[1]).resolve(strict=True)
    request = {
        "type": "request",
        "requestId": "smoke",
        "method": "todos.list",
        "params": {},
    }
    with tempfile.TemporaryDirectory(prefix="wisetodo-smoke-") as directory:
        database = Path(directory) / "smoke.db"
        for _ in range(2):
            result = subprocess.run(
                [str(binary), "--database", str(database)],
                input=json.dumps(request) + "\n",
                text=True,
                encoding="utf-8",
                capture_output=True,
                cwd=directory,
                timeout=120,
                check=True,
            )
            response = json.loads(result.stdout)
            if response.get("requestId") != "smoke" or response.get("error"):
                raise RuntimeError("Frozen backend IPC failed")
            if response.get("result") != {"todos": []}:
                raise RuntimeError("Unexpected frozen backend list result")
    print("Frozen Sidecar startup, migrations, IPC and reopen passed (offline)")


if __name__ == "__main__":
    main()
