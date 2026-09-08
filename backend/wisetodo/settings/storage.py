"""Atomic non-secret settings file and explicitly selected OS credential storage."""

import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID, uuid4

from keyring.backend import KeyringBackend
from pydantic import SecretStr

from wisetodo.settings.models import ConnectionSettings, ResolvedSettings

logger = logging.getLogger(__name__)


class SettingsStorageError(Exception):
    """Safe error text; underlying exceptions may contain credentials."""


class CredentialStore(Protocol):
    def get(self, reference: str) -> str | None: ...

    def set(self, reference: str, secret: str) -> None: ...

    def delete(self, reference: str) -> None: ...


class SystemCredentialStore:
    """Never select third-party, plaintext, null or chained fallback backends."""

    @staticmethod
    def _backend() -> KeyringBackend:
        try:
            if sys.platform == "win32":
                from keyring.backends.Windows import WinVaultKeyring

                return WinVaultKeyring()
            if sys.platform == "darwin":
                from keyring.backends.macOS import Keyring

                return Keyring()
            if sys.platform.startswith("linux"):
                from keyring.backends.SecretService import Keyring as LinuxKeyring

                return LinuxKeyring()
            raise RuntimeError("Unsupported platform")
        except Exception:
            raise SettingsStorageError("System credential storage is unavailable") from None

    def get(self, reference: str) -> str | None:
        try:
            value: str | None = self._backend().get_password("WiseTodo.Model", reference)
            return value
        except Exception:
            raise SettingsStorageError("Cannot read system credential") from None

    def set(self, reference: str, secret: str) -> None:
        try:
            self._backend().set_password("WiseTodo.Model", reference, secret)
        except Exception:
            raise SettingsStorageError("Cannot save system credential") from None

    def delete(self, reference: str) -> None:
        try:
            self._backend().delete_password("WiseTodo.Model", reference)
        except Exception:
            raise SettingsStorageError("Cannot remove system credential") from None


class StoredSettings(ConnectionSettings):
    version: Literal[1] = 1
    key_ref: UUID | None = None


class FileSettingsStore:
    """Single-writer store owned by the sidecar, never by individual sessions.

    Stage a fresh credential before replacing the file. An old credential is
    removed only after commit. A crash may leave an unreferenced OS credential,
    but cannot publish a new endpoint with the old endpoint's key.
    """

    def __init__(self, path: Path, credentials: CredentialStore) -> None:
        if not path.is_absolute():
            raise ValueError("Settings path must be absolute")
        self.path = path
        self._credentials = credentials

    def _read(self) -> StoredSettings | None:
        try:
            return StoredSettings.model_validate_json(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except Exception:
            raise SettingsStorageError("Cannot read model settings") from None

    def load(self) -> ResolvedSettings | None:
        stored = self._read()
        if stored is None:
            return None
        key = None
        if stored.key_ref is not None:
            try:
                value = self._credentials.get(str(stored.key_ref))
                if not value:
                    raise ValueError("Missing credential")
                key = SecretStr(value)
            except Exception:
                raise SettingsStorageError("Saved model credential is unavailable") from None
        return ResolvedSettings(base_url=stored.base_url, model=stored.model, api_key=key)

    def replace(self, settings: ResolvedSettings) -> None:
        previous = self._read()
        reference = uuid4() if settings.api_key is not None else None
        stored = StoredSettings(base_url=settings.base_url, model=settings.model, key_ref=reference)
        try:
            if reference is not None and settings.api_key is not None:
                self._credentials.set(str(reference), settings.api_key.get_secret_value())
                # Reject silent/no-op credential writes before publishing configuration.
                if self._credentials.get(str(reference)) != settings.api_key.get_secret_value():
                    raise ValueError("Credential verification failed")
            self._publish(stored)
        except Exception:
            if reference is not None:
                self._cleanup(reference)
            raise SettingsStorageError(
                "Cannot save model settings; previous settings retained"
            ) from None
        if previous is not None and previous.key_ref is not None:
            self._cleanup(previous.key_ref)

    def _publish(self, stored: StoredSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".settings-",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary = Path(output.name)
                output.write(stored.model_dump_json())
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def _cleanup(self, reference: UUID) -> None:
        try:
            self._credentials.delete(str(reference))
        except Exception:
            # Never turn an already committed save into a reported failure.
            logger.warning("Unused model credential cleanup failed")


def create_settings_store(data_directory: Path) -> FileSettingsStore:
    """Use the same trusted app-data directory as the SQLite database."""
    return FileSettingsStore(data_directory / "model-settings.json", SystemCredentialStore())
