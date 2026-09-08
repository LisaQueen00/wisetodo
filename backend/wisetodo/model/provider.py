from typing import Protocol, runtime_checkable

from wisetodo.model.contracts import ModelRequest, ModelResponse


@runtime_checkable
class ModelProvider(Protocol):
    """One async inference, not an Agent loop or persistence boundary.

    Concrete providers own their connection configuration; requests never carry
    credentials. Implementations must not mutate input, automatically retry,
    log raw content/secrets, execute tools or write business state.

    Preserve asyncio.CancelledError. Map transport errors to ModelRequestError
    with safe text and no raw exception chain. Streaming/SDK transport and
    connection-snapshot construction are separate implementation tasks.
    """

    async def complete(self, request: ModelRequest) -> ModelResponse: ...

    async def aclose(self) -> None:
        """Release owned clients; must be safe to call more than once."""
        ...


class ModelRequestError(Exception):
    def __init__(self) -> None:
        super().__init__("Model request failed")


class ModelCapabilityError(Exception):
    def __init__(self) -> None:
        super().__init__("Requested model capability is unavailable")
