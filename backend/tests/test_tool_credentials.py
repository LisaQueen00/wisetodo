from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from wisetodo.tools import ToolConfig, ToolRegistry
from wisetodo.tools.credentials import ToolCredentialError, ToolCredentials, ToolCredentialStore
from wisetodo.tools.transport import ToolExecutor, ToolTransportError


def test_save_and_resolve_only_references():
    store = Mock()
    vault = ToolCredentials(store)
    reference = vault.save(SecretStr("test-token"))
    store.set.assert_called_once_with(str(reference), "test-token")
    store.get.return_value = "test-token"
    assert vault.bearer_headers(reference) == {"Authorization": "Bearer test-token"}
    assert vault.bearer_headers(None) == {}


@pytest.mark.parametrize("value", [None, "", "bad\r\nheader"])
def test_missing_or_invalid_secret_fails_closed(value):
    store = Mock()
    store.get.return_value = value
    with pytest.raises(ToolCredentialError, match="^credential_unavailable$"):
        ToolCredentials(store).bearer_headers(uuid4())


def test_vault_failure_does_not_expose_secret():
    store = Mock()
    store.get.side_effect = RuntimeError("private-token")
    store.set.side_effect = RuntimeError("private-token")
    vault = ToolCredentials(store)
    with pytest.raises(ToolCredentialError, match="^credential_unavailable$"):
        vault.bearer_headers(uuid4())
    with pytest.raises(ToolCredentialError, match="^credential_save_failed$"):
        vault.save(SecretStr("private-token"))


def test_os_store_uses_separate_namespace(monkeypatch):
    backend = Mock()
    monkeypatch.setattr(
        "wisetodo.tools.credentials.SystemCredentialStore._backend", lambda: backend
    )
    store = ToolCredentialStore()
    store.set("ref", "value")
    store.get("ref")
    backend.set_password.assert_called_once_with("WiseTodo.Tools", "ref", "value")
    backend.get_password.assert_called_once_with("WiseTodo.Tools", "ref")


@pytest.mark.parametrize("available", [True, False])
async def test_http_resolves_secret_only_for_execution(available):
    reference = uuid4()
    config = ToolConfig.model_validate(
        {
            "name": "read",
            "description": "read",
            "input_schema": {"type": "object"},
            "transport": {
                "type": "http",
                "url": "https://example.org",
                "credential_ref": str(reference),
            },
        }
    )
    assert "test-token" not in config.model_dump_json()
    assert str(reference) not in config.to_definition().model_dump_json()
    store = Mock()
    store.get.return_value = "test-token" if available else None
    requests = []

    def respond(request):
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        executor = ToolExecutor(
            ToolRegistry([config]), http=client, credentials=ToolCredentials(store)
        )
        if available:
            assert await executor.execute("read", {}) == {"ok": True}
        else:
            with pytest.raises(ToolTransportError):
                await executor.execute("read", {})
            assert not requests


def test_plaintext_is_not_a_reference():
    with pytest.raises(ValidationError):
        ToolConfig.model_validate(
            {
                "name": "read",
                "description": "read",
                "input_schema": {"type": "object"},
                "transport": {
                    "type": "http",
                    "url": "https://example.org",
                    "credential_ref": "secret-token",
                },
            }
        )
