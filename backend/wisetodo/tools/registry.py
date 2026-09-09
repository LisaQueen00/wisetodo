"""Build-once tool registry snapshots, without transport activation."""

from collections.abc import Iterable
from types import MappingProxyType

from wisetodo.model.contracts import ToolDefinition
from wisetodo.tools.config import ToolConfig


class DuplicateToolNameError(ValueError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Duplicate tool name: {name}")


class ToolRegistry:
    """All transports share one case-sensitive namespace, in supplied order.

    Construct a replacement for reloads and keep the old instance for active Runs.
    Registration does not prove a handler/server exists or that a tool is safe.
    """

    def __init__(self, configs: Iterable[ToolConfig] = ()) -> None:
        entries: dict[str, ToolConfig] = {}
        for config in configs:
            # Revalidate: frozen Pydantic fields can still contain mutated dictionaries.
            detached = ToolConfig.model_validate(config.model_dump()).model_copy(deep=True)
            if detached.name in entries:
                raise DuplicateToolNameError(detached.name)
            entries[detached.name] = detached
        self._entries = MappingProxyType(entries)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._entries)

    def get(self, name: str) -> ToolConfig | None:
        config = self._entries.get(name)
        return config.model_copy(deep=True) if config is not None else None

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(config.to_definition() for config in self._entries.values())
