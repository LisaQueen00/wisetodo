"""Per-run Provider construction, independent of SDK and Session persistence."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Protocol

from wisetodo.model.provider import ModelProvider, ModelRequestError
from wisetodo.settings import ResolvedSettings, SettingsService


class ProviderFactory(Protocol):
    def __call__(self, settings: ResolvedSettings) -> ModelProvider:
        """Build a fresh client from this snapshot; never retain SettingsService.

        Construction is synchronous and must not perform network I/O. A factory
        owns cleanup if construction fails after partially allocating resources.
        """
        ...


class RunProviderScope:
    def __init__(self, settings: SettingsService, factory: ProviderFactory) -> None:
        self._settings = settings
        self._factory = factory

    @asynccontextmanager
    async def open(self) -> AsyncIterator[ModelProvider]:
        """Open once per Run, reuse for all calls and repairs, then close.

        Retry that calls the model opens a new scope; a Todo-only commit retry
        must not open one. This object does not create or persist run IDs.
        """
        snapshot = self._settings.resolve().model_copy(deep=True)
        try:
            provider = self._factory(snapshot)
        except Exception:
            raise ModelRequestError from None
        try:
            yield provider
        except BaseException:
            # Cleanup must not replace the original execution failure/cancellation.
            with suppress(Exception):
                await provider.aclose()
            raise
        else:
            try:
                await provider.aclose()
            except Exception:
                raise ModelRequestError from None
