"""Offline frozen-backend acceptance in disposable clean/existing profiles.

Never uses the real application profile, writes credentials, or sends model requests.
This is not an installer or desktop visual acceptance test.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def request(binary: Path, directory: Path, method: str, params: dict) -> dict:
    result = subprocess.run(
        [str(binary), "--database", str(directory / "acceptance.db")],
        input=json.dumps(
            {
                "type": "request",
                "requestId": "acceptance",
                "method": method,
                "params": params,
            }
        )
        + "\n",
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=directory,
        timeout=120,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    response = json.loads(result.stdout)
    if (
        not isinstance(response, dict)
        or response.get("requestId") != "acceptance"
        or response.get("error")
    ):
        raise RuntimeError(f"Acceptance IPC failed: {method}")
    if not isinstance(response.get("result"), dict):
        raise RuntimeError("Acceptance IPC result missing")  # noqa: TRY004
    return response["result"]


def accept(binary: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="wisetodo-release-") as temporary:
        directory = Path(temporary)
        if request(binary, directory, "todos.list", {}) != {"todos": []}:
            raise RuntimeError("Clean profile contains unexpected Todos")
        if request(binary, directory, "settings.get", {}) != {"settings": None}:
            raise RuntimeError("Clean profile contains unexpected model settings")
        created = request(
            binary,
            directory,
            "user.todos.create",
            {
                "todo": {
                    "topic": "Offline acceptance",
                    "priority": 1,
                    "items": ["Read source", "Run tests"],
                },
            },
        )["todo"]
        # Synthetic non-secret existing settings: no credential reference or network calls.
        config = json.dumps(
            {
                "version": 1,
                "base_url": "http://127.0.0.1:9/v1",
                "model": "offline-acceptance",
                "key_ref": None,
            }
        )
        tools = '{"tools":[],"servers":[]}'
        (directory / "model-settings.json").write_text(config, encoding="utf-8")
        (directory / "tool-settings.json").write_text(tools, encoding="utf-8")
        (directory / "skills").mkdir()
        rows = request(binary, directory, "todos.list", {})["todos"]
        if rows != [created]:
            raise RuntimeError("Existing Todo was not retained on reopen")
        settings = request(binary, directory, "settings.get", {})["settings"]
        if settings["model"] != "offline-acceptance" or settings["has_api_key"]:
            raise RuntimeError("Existing settings were not retained")
        updated = request(
            binary,
            directory,
            "user.todos.set_item_completed",
            {
                "todo_id": created["id"],
                "item_id": created["items"][0]["id"],
                "completed": True,
            },
        )["todo"]
        if not updated["items"][0]["completed"] or updated["completed"]:
            raise RuntimeError("Subitem completion failed")
        if request(binary, directory, "todos.list", {})["todos"] != [updated]:
            raise RuntimeError("Updated Todo was not retained")
        for name, content in (
            ("model-settings.json", config),
            ("tool-settings.json", tools),
        ):
            if (directory / name).read_text(encoding="utf-8") != content:
                raise RuntimeError("Existing configuration was rewritten")
        if list((directory / "skills").iterdir()):
            raise RuntimeError("Explicit empty Skill directory was overwritten")
    print(
        "PASS: clean profile, existing configuration, Todo create/update/reopen (offline)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    accept(parser.parse_args().binary.resolve(strict=True))
