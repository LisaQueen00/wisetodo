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


@pytest.mark.parametrize("key_action", ["clear", "replace"])
async def test_repair_keeps_snapshot_when_settings_change(key_action: str) -> None:
    from wisetodo.agent.generation import ResultGenerator
    from wisetodo.agent.prompts import build_agent_request

    store, settings, _, _ = setup()
    created = []

    class RepairProvider(Provider):
        calls = 0

        async def complete(self, request: ModelRequest) -> ModelResponse:
            self.calls += 1
            if len(created) == 1 and self.calls == 1:
                payload = {
                    "base_url": "https://second.example/v1",
                    "model": "second",
                    "key_action": key_action,
                }
                if key_action == "replace":
                    payload["api_key"] = "second-secret"
                settings.save(SettingsUpdate.model_validate(payload))
                return ModelResponse(content="invalid JSON", finish_reason="stop")
            return ModelResponse(
                content='{"type":"clarification","question":"哪本书？"}', finish_reason="stop"
            )

    def factory(config: ResolvedSettings) -> RepairProvider:
        provider = RepairProvider(config)
        created.append(provider)
        return provider

    scope = RunProviderScope(settings, factory)
    request = build_agent_request([ModelMessage(role="user", content="读书")])
    async with scope.open() as provider:
        await ResultGenerator(provider).generate(request)
        assert created[0].calls == 2
        assert created[0].settings.model == "first"
        assert created[0].settings.base_url == "https://first.example/v1"
        assert created[0].settings.api_key.get_secret_value() == "first-secret"
        assert store.reads == 1
    async with scope.open() as provider:
        await ResultGenerator(provider).generate(request)
        assert created[1].settings.model == "second"
        assert created[1].settings.base_url == "https://second.example/v1"
        if key_action == "clear":
            assert created[1].settings.api_key is None
        else:
            assert created[1].settings.api_key.get_secret_value() == "second-secret"
    assert store.reads == 2
    assert [provider.closed for provider in created] == [1, 1]


async def test_pending_commit_retry_does_not_read_broken_settings(tmp_path) -> None:
    from uuid import uuid4

    from sqlalchemy import event
    from sqlalchemy.exc import SQLAlchemyError

    from wisetodo.agent.runtime import AgentRuntime
    from wisetodo.database import initialize_database
    from wisetodo.sessions.models import ChatInput
    from wisetodo.sessions.retry import RetryExecutionError
    from wisetodo.sessions.service import SessionService
    from wisetodo.sessions.tables import SessionRecord
    from wisetodo.todos import TodoService

    store, settings, _, _ = setup()
    providers = []

    class CreateProvider(Provider):
        async def complete(self, request: ModelRequest) -> ModelResponse:
            return ModelResponse(
                content=(
                    '{"type":"todo_operation","operation":{"action":"create",'
                    '"todo":{"topic":"test","items":["one","two"]}}}'
                ),
                finish_reason="stop",
            )

    def factory(config: ResolvedSettings) -> CreateProvider:
        provider = CreateProvider(config)
        providers.append(provider)
        return provider

    database = initialize_database(tmp_path / "pending.db")
    try:
        sessions = SessionService(database.sessions)
        todos = TodoService(database.sessions)
        sessions.agent_executor = AgentRuntime(sessions, todos, RunProviderScope(settings, factory))
        session_id = sessions.create().id

        def fail_commit(transaction):
            if any(
                isinstance(row, SessionRecord) and row.status == "completed"
                for row in transaction.identity_map.values()
            ):
                raise SQLAlchemyError("simulated write failure")

        event.listen(database.sessions, "before_commit", fail_commit)
        try:
            with pytest.raises(RetryExecutionError):
                await sessions.submit(session_id, ChatInput(message_id=uuid4(), content="test"))
        finally:
            event.remove(database.sessions, "before_commit", fail_commit)
        assert todos.list() == []
        assert store.reads == 1
        store.broken = True  # Simulate lost/unavailable credentials after generation.
        result = await sessions.retry(session_id)
        assert result.status == "completed"
        assert len(todos.list()) == 1
        assert store.reads == 1 and len(providers) == 1
        assert providers[0].closed == 1
        assert "first-secret" not in result.model_dump_json()
    finally:
        database.dispose()
