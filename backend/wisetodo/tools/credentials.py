"""Tool credentials live in the OS vault, never in tool configuration files."""

from uuid import UUID, uuid4

from pydantic import SecretStr

from wisetodo.settings.storage import CredentialStore, SystemCredentialStore


class ToolCredentialError(RuntimeError):
    pass


class ToolCredentialStore:
    def get(self, reference: str) -> str | None:
        return SystemCredentialStore._backend().get_password("WiseTodo.Tools", reference)

    def set(self, reference: str, secret: str) -> None:
        SystemCredentialStore._backend().set_password("WiseTodo.Tools", reference, secret)

    def delete(self, reference: str) -> None:
        SystemCredentialStore._backend().delete_password("WiseTodo.Tools", reference)


class ToolCredentials:
    def __init__(self, store: CredentialStore | None = None) -> None:
        self._store = store if store is not None else ToolCredentialStore()

    def save(self, secret: SecretStr) -> UUID:
        reference = uuid4()
        try:
            value = secret.get_secret_value()
            if not value or any(char.isspace() or ord(char) < 32 for char in value):
                raise ValueError("invalid bearer credential")
            self._store.set(str(reference), value)
        except Exception:
            raise ToolCredentialError("credential_save_failed") from None
        return reference

    def bearer_headers(self, reference: UUID | None) -> dict[str, str]:
        if reference is None:
            return {}
        try:
            value = self._store.get(str(reference))
            if not value or any(char.isspace() or ord(char) < 32 for char in value):
                raise ValueError("invalid bearer credential")
            return {"Authorization": f"Bearer {value}"}
        except Exception:
            raise ToolCredentialError("credential_unavailable") from None

    def delete(self, reference: UUID) -> None:
        try:
            self._store.delete(str(reference))
        except Exception:
            raise ToolCredentialError("credential_delete_failed") from None
