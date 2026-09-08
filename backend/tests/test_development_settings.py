import json
import subprocess
import sys
from pathlib import Path

import pytest

from wisetodo.settings import ResolvedSettings, SettingsService, SettingsUpdate
from wisetodo.settings.development import DevelopmentSettingsStore
from wisetodo.settings.storage import SettingsStorageError


class Store:
    value: ResolvedSettings | None = None
    broken = False

    def load(self) -> ResolvedSettings | None:
        if self.broken:
            raise SettingsStorageError("Primary failed")
        return self.value

    def replace(self, value: ResolvedSettings) -> None:
        self.value = value


def config(tmp_path: Path, **extra: object) -> Path:
    path = tmp_path / "model-settings.dev.json"
    path.write_text(
        json.dumps({"base_url": "http://localhost:8000/v1", "model": "dev", **extra}),
        encoding="utf-8",
    )
    return path


def test_disabled_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = config(tmp_path)
    monkeypatch.setenv("WISETODO_DEV_MODEL_CONFIG", str(path))
    assert DevelopmentSettingsStore(Store()).load() is None


def test_reads_whole_config_and_resolves_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = config(tmp_path, api_key_env="WISETODO_TEST_KEY")
    monkeypatch.setenv("WISETODO_TEST_KEY", "private-secret")
    service = SettingsService(DevelopmentSettingsStore(Store(), path))
    assert service.get().model == "dev"
    assert service.resolve().api_key.get_secret_value() == "private-secret"
    assert "private-secret" not in service.get().model_dump_json()
    assert "private-secret" not in path.read_text()


def test_primary_wins_even_without_key_and_invalid_fallback(tmp_path: Path) -> None:
    primary = Store()
    primary.value = ResolvedSettings(base_url="https://example.com", model="ui")
    assert DevelopmentSettingsStore(primary, tmp_path / "missing.json").load() == primary.value


def test_primary_error_does_not_fall_back(tmp_path: Path) -> None:
    primary = Store()
    primary.broken = True
    with pytest.raises(SettingsStorageError, match="Primary"):
        DevelopmentSettingsStore(primary, config(tmp_path)).load()


@pytest.mark.parametrize(
    "extra",
    [
        {"api_key": "private-secret"},
        {"api_key_env": ""},
        {"api_key_env": "invalid-name"},
        {"api_key_env": "WISETODO_MISSING_TEST_KEY"},
        {"base_url": "invalid"},
        {"model": ""},
    ],
)
def test_bad_config_is_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: dict
) -> None:
    monkeypatch.delenv("WISETODO_MISSING_TEST_KEY", raising=False)
    with pytest.raises(SettingsStorageError) as error:
        DevelopmentSettingsStore(Store(), config(tmp_path, **extra)).load()
    assert "private-secret" not in str(error.value)


def test_ui_save_takes_over_without_modifying_file(tmp_path: Path) -> None:
    path = config(tmp_path)
    original = path.read_bytes()
    primary = Store()
    service = SettingsService(DevelopmentSettingsStore(primary, path))
    service.save(SettingsUpdate(base_url="https://example.com", model="ui", key_action="clear"))
    assert service.get().model == "ui"
    assert path.read_bytes() == original
    assert SettingsService(DevelopmentSettingsStore(primary)).get().model == "ui"


def test_relative_and_missing_path_fail(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        DevelopmentSettingsStore(Store(), Path("relative.json"))
    with pytest.raises(SettingsStorageError):
        DevelopmentSettingsStore(Store(), tmp_path / "missing.json").load()


def test_explicit_sidecar_flag(tmp_path: Path) -> None:
    path = config(tmp_path)
    message = (
        json.dumps({"type": "request", "requestId": "1", "method": "settings.get", "params": {}})
        + "\n"
    )
    command = [sys.executable, "-m", "wisetodo.main", "--database", str(tmp_path / "test.db")]
    for arguments, expected in [([], None), (["--dev-model-config", str(path)], "dev")]:
        result = subprocess.run(
            command + arguments,
            input=message,
            encoding="utf-8",
            capture_output=True,
            cwd=tmp_path,
            timeout=20,
        )
        assert result.returncode == 0, result.stderr
        value = json.loads(result.stdout)["result"]["settings"]
        assert (value["model"] if value else None) == expected
