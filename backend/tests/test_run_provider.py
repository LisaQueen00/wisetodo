import asyncio

import pytest

from wisetodo.model import (
    ModelMessage,
    ModelRequest,
    ModelRequestError,
    ModelResponse,
    RunProviderScope,
)
from wisetodo.settings import (
    ResolvedSettings,
    SettingsNotConfiguredError,
    SettingsService,
    SettingsUpdate,
)
from wisetodo.settings.storage import SettingsStorageError


class Store:
    value: ResolvedSettings | None = None
    reads = 0
    broken = False

    def load(self) -> ResolvedSettings | None:
        self.reads += 1
        if self.broken:
            raise SettingsStorageError("Settings unavailable")
        return self.value

    def replace(self, value: ResolvedSettings) -> None:
        self.value = value


class Provider:
    def __init__(self, settings: ResolvedSettings) -> None:
        self.settings = settings
        self.closed = 0
        self.fail_close = False

    async def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content=self.settings.model, finish_reason="stop")

    async def aclose(self) -> None:
        self.closed += 1
        if self.fail_close:
            raise RuntimeError("private-secret")


def setup() -> tuple[Store, SettingsService, list[Provider], RunProviderScope]:
    store = Store()
    service = SettingsService(store)
    service.save(
        SettingsUpdate.model_validate(
            {
                "base_url": "https://first.example/v1",
                "model": "first",
                "key_action": "replace",
                "api_key": "first-secret",
            }
        )
    )
    providers: list[Provider] = []

    def factory(settings: ResolvedSettings) -> Provider:
        provider = Provider(settings)
        providers.append(provider)
        return provider

    return store, service, providers, RunProviderScope(service, factory)


async def test_one_snapshot_per_run_and_next_run_uses_new_settings() -> None:
    store, settings, providers, scope = setup()
    request = ModelRequest(messages=(ModelMessage(role="user", content="hello"),))
    async with scope.open() as first:
        assert store.reads == 1
        assert (await first.complete(request)).content == "first"
        settings.save(
            SettingsUpdate(base_url="http://localhost:8000/v1", model="second", key_action="clear")
        )
        assert (await first.complete(request)).content == "first"
        assert store.reads == 1
        assert providers[0].settings.api_key.get_secret_value() == "first-secret"
        assert "first-secret" not in repr(providers[0].settings)
        assert "first-secret" not in providers[0].settings.model_dump_json()
        async with scope.open() as second:
            assert (await second.complete(request)).content == "second"
            assert providers[1].settings.api_key is None
            assert second is not first
        assert providers[0].closed == 0
    assert [provider.closed for provider in providers] == [1, 1]
    assert store.reads == 2


@pytest.mark.parametrize("broken", [False, True])
async def test_configuration_failure_prevents_factory(broken: bool) -> None:
    store = Store()
    store.broken = broken
    called = False

    def factory(settings: ResolvedSettings) -> Provider:
        nonlocal called
        called = True
        return Provider(settings)

    scope = RunProviderScope(SettingsService(store), factory)
    with pytest.raises(SettingsStorageError if broken else SettingsNotConfiguredError):
        async with scope.open():
            pytest.fail("Must not enter")
    assert not called


async def test_factory_errors_hide_credentials() -> None:
    _, settings, _, _ = setup()

    def fail(config: ResolvedSettings) -> Provider:
        raise RuntimeError("private-secret")

    with pytest.raises(ModelRequestError) as error:
        async with RunProviderScope(settings, fail).open():
            pytest.fail("Must not enter")
    assert "private-secret" not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize("cancel", [False, True])
async def test_closes_on_failure_without_masking_original(cancel: bool) -> None:
    _, _, providers, scope = setup()
    failure = asyncio.CancelledError() if cancel else ValueError("original")
    with pytest.raises(type(failure)) as caught:
        async with scope.open():
            providers[0].fail_close = True
            raise failure
    assert caught.value is failure
    assert providers[0].closed == 1


async def test_close_failure_after_success_is_safe() -> None:
    _, _, providers, scope = setup()
    with pytest.raises(ModelRequestError) as caught:
        async with scope.open():
            providers[0].fail_close = True
    assert "private-secret" not in str(caught.value)
