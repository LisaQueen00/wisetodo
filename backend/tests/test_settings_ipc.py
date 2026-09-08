import io
import json
from pathlib import Path

import pytest

from wisetodo.ipc.server import run_stdio_server
from wisetodo.settings import ResolvedSettings, SettingsService
from wisetodo.settings.storage import SettingsStorageError


class Store:
    value: ResolvedSettings | None = None
    fail = False

    def load(self) -> ResolvedSettings | None:
        if self.fail:
            raise SettingsStorageError("private-secret")
        return self.value

    def replace(self, value: ResolvedSettings) -> None:
        if self.fail:
            raise SettingsStorageError("private-secret")
        self.value = value


def req(method: str, params: object) -> dict[str, object]:
    return {"type": "request", "requestId": "settings-test", "method": method, "params": params}


async def exchange(
    monkeypatch: pytest.MonkeyPatch, store: Store, requests: list[dict[str, object]]
) -> str:
    output = io.StringIO()
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(map(json.dumps, requests)) + "\n"))
    monkeypatch.setattr("sys.stdout", output)
    await run_stdio_server(settings_service=SettingsService(store))
    return output.getvalue()


async def test_fixed_settings_commands_and_redacted_key_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Store()
    base = {"base_url": "http://localhost:8000/v1", "model": "test"}
    output = await exchange(
        monkeypatch,
        store,
        [
            req("settings.get", {}),
            req(
                "user.settings.save",
                {"settings": {**base, "key_action": "replace", "api_key": "private-secret"}},
            ),
            req("user.settings.save", {"settings": base}),
            req("settings.get", {}),
        ],
    )
    rows = list(map(json.loads, output.splitlines()))
    assert rows[0]["result"] == {"settings": None}
    assert all(row["result"]["settings"]["has_api_key"] for row in rows[1:])
    assert "private-secret" not in output
    assert store.value.api_key.get_secret_value() == "private-secret"
    cleared = await exchange(
        monkeypatch,
        store,
        [
            req("user.settings.save", {"settings": {**base, "key_action": "clear"}}),
        ],
    )
    assert not json.loads(cleared)["result"]["settings"]["has_api_key"]
    assert store.value.api_key is None


@pytest.mark.parametrize(
    "method,params,code",
    [
        ("settings.get", {"path": "private-secret"}, "SETTINGS_VALIDATION_FAILED"),
        (
            "user.settings.save",
            {"settings": {"api_key": "private-secret"}},
            "SETTINGS_VALIDATION_FAILED",
        ),
        ("agent.settings.save", {}, "IPC_METHOD_NOT_FOUND"),
    ],
)
async def test_invalid_requests_never_echo_input(
    monkeypatch: pytest.MonkeyPatch, method: str, params: dict, code: str
) -> None:
    output = await exchange(monkeypatch, Store(), [req(method, params)])
    assert json.loads(output)["error"]["code"] == code
    assert "private-secret" not in output


@pytest.mark.parametrize("method", ["settings.get", "user.settings.save"])
async def test_storage_failure_is_redacted(monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    store = Store()
    store.fail = True
    params = (
        {}
        if method == "settings.get"
        else {"settings": {"base_url": "http://localhost", "model": "test"}}
    )
    output = await exchange(monkeypatch, store, [req(method, params)])
    assert json.loads(output)["error"]["code"] == (
        "SETTINGS_READ_FAILED" if method == "settings.get" else "SETTINGS_SAVE_FAILED"
    )
    assert "private-secret" not in output


def test_real_sidecar_settings_survive_restart(tmp_path: Path) -> None:
    from test_sidecar import run_sidecar

    path = tmp_path / "wisetodo.db"
    saved = run_sidecar(
        path,
        [
            req(
                "user.settings.save",
                {"settings": {"base_url": "http://localhost:8000/v1", "model": "local"}},
            )
        ],
        tmp_path,
    )
    assert saved.returncode == 0, saved.stderr
    read = run_sidecar(path, [req("settings.get", {})], tmp_path)
    assert read.returncode == 0, read.stderr
    assert json.loads(read.stdout)["result"] == json.loads(saved.stdout)["result"]
    assert (tmp_path / "model-settings.json").is_file()
