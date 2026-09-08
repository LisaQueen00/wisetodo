"""Global connection settings; secrets must never be returned to the UI."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    SecretStr,
    StrictStr,
    field_validator,
    model_validator,
)


class ConnectionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    base_url: StrictStr
    model: StrictStr

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, raw: str) -> str:
        value = raw.strip()
        if any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c == "\\" for c in value):
            raise ValueError("Invalid base URL characters")
        parsed = urlsplit(value)
        if (
            not value.lower().startswith(("http://", "https://"))
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or "?" in value
            or "#" in value
        ):
            raise ValueError("Expected HTTP(S) base URL without credentials, query or fragment")
        _ = parsed.port
        HttpUrl(value)
        return value  # Preserve provider paths; do not append /v1 automatically.

    @field_validator("model")
    @classmethod
    def validate_model(cls, raw: str) -> str:
        value = raw.strip()
        if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Model name must be nonempty and contain no control characters")
        return value


class SettingsUpdate(ConnectionSettings):
    key_action: Literal["keep", "replace", "clear"] = "keep"
    api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_key_action(self) -> "SettingsUpdate":
        if self.key_action == "replace":
            value = self.api_key.get_secret_value() if self.api_key is not None else ""
            if not value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError("Replacement API key must be nonempty and contain no whitespace")
        elif self.api_key is not None:
            raise ValueError("API key is accepted only for the replace action")
        return self


class ResolvedSettings(ConnectionSettings):
    """Internal immutable snapshot, not an IPC response or persistence format."""

    api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)


class SettingsView(ConnectionSettings):
    has_api_key: bool
