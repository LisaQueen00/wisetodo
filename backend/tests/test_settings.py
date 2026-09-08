import pytest
from pydantic import ValidationError

from wisetodo.settings import (
    ResolvedSettings,
    SettingsNotConfiguredError,
    SettingsService,
    SettingsUpdate,
)


class MemoryStore:
    def __init__(self) -> None:
        self.value: ResolvedSettings | None = None
        self.fail = False

    def load(self) -> ResolvedSettings | None:
        return self.value

    def replace(self, settings: ResolvedSettings) -> None:
        if self.fail:
            raise OSError("Storage unavailable")
        self.value = settings


def update(**changes: object) -> SettingsUpdate:
    return SettingsUpdate.model_validate(
        {"base_url": "http://localhost:11434/v1", "model": "local-model", **changes}
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434/v1",
        "http://127.0.0.1:8000",
        "http://[::1]:8000/v1",
        "https://example.com/custom/api/",
    ],
)
def test_accepts_cloud_and_local_urls(url: str) -> None:
    settings = update(base_url=f" {url} ", model=" model/name ")
    assert settings.base_url == url
    assert settings.model == "model/name"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "localhost:8000",
        "file:///tmp/key",
        "https://",
        "https://user:key@example.com",
        "https://@example.com",
        "https://example.com?key=secret",
        "https://example.com#",
        "https://example.com:99999",
        "https://exam ple.com",
        "https://example.com\\path",
        "https://example.com/\npath",
    ],
)
def test_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        update(base_url=url)


@pytest.mark.parametrize(
    "changes",
    [
        {"model": " "},
        {"model": 42},
        {"model": "a\nb"},
        {"base_url": 42},
        {"session_id": "not-global"},
        {"key_action": "unknown"},
        {"key_action": "replace"},
        {"key_action": "replace", "api_key": ""},
        {"key_action": "replace", "api_key": " a "},
        {"api_key": "secret"},
        {"key_action": "clear", "api_key": "secret"},
    ],
)
def test_rejects_invalid_fields(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        update(**changes)


def test_unconfigured_and_local_without_key() -> None:
    store = MemoryStore()
    service = SettingsService(store)
    assert service.get() is None
    with pytest.raises(SettingsNotConfiguredError):
        service.resolve()
    assert not service.save(update()).has_api_key
    assert service.resolve().api_key is None
    assert SettingsService(store).get() == service.get()


def test_key_lifecycle_and_safe_views() -> None:
    service = SettingsService(MemoryStore())
    request = update(key_action="replace", api_key="secret-one")
    view = service.save(request)
    snapshot = service.resolve()
    assert view.has_api_key
    for value in (request, view, snapshot):
        assert "secret-one" not in repr(value)
        assert "api_key" not in value.model_dump()
        assert "secret-one" not in value.model_dump_json()
    service.save(update(model="different"))
    assert service.resolve().api_key == snapshot.api_key
    service.save(update(key_action="replace", api_key="secret-two"))
    assert service.resolve().api_key != snapshot.api_key
    assert snapshot.api_key is not None
    assert snapshot.api_key.get_secret_value() == "secret-one"
    with pytest.raises(ValidationError):
        snapshot.model = "mutation"
    assert not service.save(update(key_action="clear")).has_api_key
    assert service.resolve().api_key is None


def test_changed_endpoint_cannot_silently_reuse_key() -> None:
    service = SettingsService(MemoryStore())
    service.save(update(key_action="replace", api_key="secret"))
    previous = service.get()
    with pytest.raises(ValueError, match="base URL"):
        service.save(update(base_url="https://another.example/v1"))
    assert service.get() == previous
    assert not service.save(
        update(base_url="https://another.example/v1", key_action="clear")
    ).has_api_key


def test_failed_save_keeps_previous_settings() -> None:
    store = MemoryStore()
    service = SettingsService(store)
    previous = service.save(update(key_action="replace", api_key="secret"))
    store.fail = True
    with pytest.raises(OSError):
        service.save(update(model="new-model", key_action="clear"))
    assert service.get() == previous


def test_validation_error_text_hides_input() -> None:
    with pytest.raises(ValidationError) as caught:
        update(key_action="replace", api_key="private key")
    assert "private key" not in str(caught.value)
    # Structured Pydantic errors must also be explicitly redacted by future IPC.
    assert "private key" not in str(caught.value.errors(include_input=False))
