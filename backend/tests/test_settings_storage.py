import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

from wisetodo.settings import SettingsService, SettingsUpdate
from wisetodo.settings.storage import (
    FileSettingsStore,
    SettingsStorageError,
    SystemCredentialStore,
    create_settings_store,
)


class Credentials:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.fail_set = False
        self.fail_delete = False

    def get(self, reference: str) -> str | None:
        return self.values.get(reference)

    def set(self, reference: str, secret: str) -> None:
        if self.fail_set:
            raise RuntimeError("sensitive-error-content")
        self.values[reference] = secret

    def delete(self, reference: str) -> None:
        if self.fail_delete:
            raise RuntimeError("sensitive-error-content")
        self.values.pop(reference, None)


def request(**changes: object) -> SettingsUpdate:
    return SettingsUpdate.model_validate(
        {
            "base_url": "http://localhost:8000/v1",
            "model": "test",
            **changes,
        }
    )


def test_reopen_persists_settings_without_serializing_key(tmp_path: Path) -> None:
    credentials = Credentials()
    path = tmp_path / "model-settings.json"
    service = SettingsService(FileSettingsStore(path, credentials))
    assert service.get() is None
    view = service.save(request(key_action="replace", api_key="test-secret"))
    assert "test-secret" not in path.read_text()
    assert set(json.loads(path.read_text())) == {"version", "base_url", "model", "key_ref"}
    reopened = SettingsService(FileSettingsStore(path, credentials))
    assert reopened.get() == view
    assert reopened.resolve().api_key.get_secret_value() == "test-secret"
    reopened.save(request(model="updated"))
    assert len(credentials.values) == 1
    reopened.save(request(key_action="clear"))
    assert credentials.values == {}
    assert not SettingsService(FileSettingsStore(path, credentials)).get().has_api_key


def test_local_service_does_not_access_credential_backend(tmp_path: Path) -> None:
    credentials = Credentials()
    credentials.fail_set = True
    service = SettingsService(FileSettingsStore(tmp_path / "settings.json", credentials))
    assert not service.save(request()).has_api_key
    assert service.resolve().api_key is None


@pytest.mark.parametrize("failure", ["credential", "file"])
def test_failed_save_preserves_old_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    credentials = Credentials()
    store = FileSettingsStore(tmp_path / "settings.json", credentials)
    service = SettingsService(store)
    service.save(request(key_action="replace", api_key="old-secret"))
    before = store.path.read_bytes()
    if failure == "credential":
        credentials.fail_set = True
    else:

        def fail(*args: object) -> None:
            raise OSError("sensitive-error-content")

        monkeypatch.setattr("wisetodo.settings.storage.os.replace", fail)
    with pytest.raises(SettingsStorageError) as caught:
        service.save(request(model="changed", key_action="replace", api_key="new-secret"))
    assert "sensitive-error-content" not in str(caught.value)
    assert store.path.read_bytes() == before
    assert list(credentials.values.values()) == ["old-secret"]
    assert list(tmp_path.glob(".settings-*.tmp")) == []


def test_cleanup_failure_is_not_reported_as_failed_commit(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Alembic logging setup in earlier tests may disable existing named loggers.
    monkeypatch.setattr(logging.getLogger("wisetodo.settings.storage"), "disabled", False)
    credentials = Credentials()
    service = SettingsService(FileSettingsStore(tmp_path / "settings.json", credentials))
    service.save(request(key_action="replace", api_key="old-secret"))
    credentials.fail_delete = True
    assert not service.save(request(key_action="clear")).has_api_key
    assert service.resolve().api_key is None
    assert "cleanup failed" in caplog.text
    assert "sensitive-error-content" not in caplog.text
    assert "old-secret" not in caplog.text


@pytest.mark.parametrize("action", ["clear", "replace"])
def test_missing_credential_errors_but_can_be_explicitly_repaired(
    tmp_path: Path,
    action: str,
) -> None:
    credentials = Credentials()
    service = SettingsService(FileSettingsStore(tmp_path / "settings.json", credentials))
    service.save(request(key_action="replace", api_key="lost-secret"))
    credentials.values.clear()
    with pytest.raises(SettingsStorageError, match="unavailable"):
        service.get()
    changes = {"api_key": "replacement"} if action == "replace" else {}
    assert service.save(request(key_action=action, **changes)).has_api_key == (action == "replace")


@pytest.mark.parametrize("contents", ["not json", '{"version": 2}', '{"api_key": "secret"}'])
def test_corrupt_file_is_not_overwritten(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "settings.json"
    path.write_text(contents)
    service = SettingsService(FileSettingsStore(path, Credentials()))
    with pytest.raises(SettingsStorageError):
        service.get()
    with pytest.raises(SettingsStorageError):
        service.save(request(key_action="clear"))
    assert path.read_text() == contents


def test_factory_uses_trusted_absolute_app_directory(tmp_path: Path) -> None:
    store = create_settings_store(tmp_path)
    assert store.path == tmp_path / "model-settings.json"
    assert store.load() is None
    with pytest.raises(ValueError):
        create_settings_store(Path("relative"))


@pytest.mark.parametrize("operation", ["get", "set", "delete"])
def test_system_backend_errors_are_safe(monkeypatch: pytest.MonkeyPatch, operation: str) -> None:
    def fail() -> None:
        raise RuntimeError("sensitive-error-content")

    monkeypatch.setattr(SystemCredentialStore, "_backend", staticmethod(fail))
    store = SystemCredentialStore()
    with pytest.raises(SettingsStorageError) as caught:
        if operation == "set":
            store.set("reference", "secret")
        else:
            getattr(store, operation)("reference")
    assert "sensitive-error-content" not in str(caught.value)


def test_unsupported_platform_never_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("wisetodo.settings.storage.sys.platform", "unsupported")
    with pytest.raises(SettingsStorageError):
        SystemCredentialStore().set("reference", "secret")


def test_real_process_restart_reads_nonsecret_settings(tmp_path: Path) -> None:
    service = SettingsService(create_settings_store(tmp_path))
    service.save(request())
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from pathlib import Path; "
            "from wisetodo.settings.storage import create_settings_store; "
            "from wisetodo.settings import SettingsService; "
            "print(SettingsService(create_settings_store(Path(sys.argv[1]))).get().model_dump_json())",
            str(tmp_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert json.loads(result.stdout) == service.get().model_dump()


def test_system_adapter_forwards_to_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    values: dict[tuple[str, str], str] = {}

    class Backend:
        def get_password(self, service: str, user: str) -> str | None:
            return values.get((service, user))

        def set_password(self, service: str, user: str, password: str) -> None:
            values[service, user] = password

        def delete_password(self, service: str, user: str) -> None:
            del values[service, user]

    monkeypatch.setattr(SystemCredentialStore, "_backend", staticmethod(Backend))
    adapter = SystemCredentialStore()
    adapter.set("reference", "secret")
    assert values == {("WiseTodo.Model", "reference"): "secret"}
    assert adapter.get("reference") == "secret"
    adapter.delete("reference")
    assert adapter.get("reference") is None
