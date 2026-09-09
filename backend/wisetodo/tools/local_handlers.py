"""Production allowlist of reviewed asynchronous, read-only local handlers."""

from wisetodo.tools.transport import LocalHandler


def registered_handlers() -> dict[str, LocalHandler]:
    """Register business handlers here in Phase 5, not via arbitrary module imports.

    A handler accepts a detached JSON argument object and returns a JSON value.
    It must cooperate with cancellation and avoid blocking the event loop.
    Configuration may alias existing handlers without recompilation; adding Python
    implementations remains an application code change (or use an external MCP server).
    """
    return {}
