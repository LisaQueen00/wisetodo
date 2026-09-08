"""Explicit, read-only development fallback; never merge configuration fields."""

import os
from pathlib import Path

from pydantic import StrictStr, field_validator

from wisetodo.settings.models import ConnectionSettings, ResolvedSettings, SettingsUpdate
from wisetodo.settings.service import SettingsStore
from wisetodo.settings.storage import SettingsStorageError


class DevelopmentSettings(ConnectionSettings):
    api_key_env: StrictStr | None = None

    @field_validator("api_key_env")
    @classmethod
    def validate_reference(cls, value: str | None) -> str | None:
        if value is not None and (not value.isascii() or not value.isidentifier()):
            raise ValueError("Expected an environment variable name")
        return value


class DevelopmentSettingsStore:
    def __init__(self, primary: SettingsStore, path: Path | None = None) -> None:
        if path is not None and not path.is_absolute():
            raise ValueError("Development settings path must be absolute")
        self._primary = primary
        self._path = path

    def load(self) -> ResolvedSettings | None:
        # A broken UI configuration must raise, not fall back to another endpoint.
        configured = self._primary.load()
        if configured is not None or self._path is None:
            return configured
        try:
            config = DevelopmentSettings.model_validate_json(
                self._path.read_text(encoding="utf-8-sig")
            )
            key = None
            if config.api_key_env is not None:
                # Reuse key validation too; never accept an absent referenced secret.
                validated = SettingsUpdate.model_validate(
                    {
                        "base_url": config.base_url,
                        "model": config.model,
                        "key_action": "replace",
                        "api_key": os.environ.get(config.api_key_env),
                    }
                )
                key = validated.api_key
            return ResolvedSettings(base_url=config.base_url, model=config.model, api_key=key)
        except Exception:
            raise SettingsStorageError("Cannot load development model settings") from None

    def replace(self, settings: ResolvedSettings) -> None:
        # UI saves always go to production storage; source file is never modified.
        self._primary.replace(settings)
