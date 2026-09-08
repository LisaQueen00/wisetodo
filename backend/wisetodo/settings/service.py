from typing import Protocol

from wisetodo.settings.models import ResolvedSettings, SettingsUpdate, SettingsView


class SettingsNotConfiguredError(Exception):
    def __init__(self) -> None:
        super().__init__("Model connection is not configured")


class SettingsStore(Protocol):
    """Trusted storage boundary; implementations must protect credentials.

    replace must publish a complete configuration or leave the previous one intact.
    Implementations must not serialize ResolvedSettings as a credential file.
    FileSettingsStore supplies persistent settings and system credential adapters.
    """

    def load(self) -> ResolvedSettings | None: ...

    def replace(self, settings: ResolvedSettings) -> None: ...


class SettingsService:
    """One global connection, independent of sessions and model execution."""

    def __init__(self, store: SettingsStore) -> None:
        self._store = store

    def get(self) -> SettingsView | None:
        settings = self._store.load()
        return None if settings is None else self._view(settings)

    def save(self, update: SettingsUpdate) -> SettingsView:
        # Explicit replacement/clear must also work if an old credential was lost.
        previous = self._store.load() if update.key_action == "keep" else None
        key = previous.api_key if previous is not None else None
        if (
            previous is not None
            and key is not None
            and previous.base_url != update.base_url
            and update.key_action == "keep"
        ):
            raise ValueError("Changing base URL requires explicitly replacing or clearing the key")
        if update.key_action == "replace":
            key = update.api_key
        elif update.key_action == "clear":
            key = None
        settings = ResolvedSettings(base_url=update.base_url, model=update.model, api_key=key)
        self._store.replace(settings)
        return self._view(settings)

    def resolve(self) -> ResolvedSettings:
        """For trusted Provider callers only; never return this through IPC."""
        settings = self._store.load()
        if settings is None:
            raise SettingsNotConfiguredError
        return settings.model_copy()

    @staticmethod
    def _view(settings: ResolvedSettings) -> SettingsView:
        return SettingsView(
            base_url=settings.base_url,
            model=settings.model,
            has_api_key=settings.api_key is not None,
        )
