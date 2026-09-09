"""Production allowlist of reviewed asynchronous, read-only local handlers."""

from wisetodo.files.pdf_tool import pdf_handler
from wisetodo.files.references import FileReferences
from wisetodo.tools.transport import LocalHandler


def registered_handlers(references: FileReferences | None = None) -> dict[str, LocalHandler]:
    """Bind reviewed business handlers, not arbitrary module imports.

    A handler accepts a detached JSON argument object and returns a JSON value.
    It must cooperate with cancellation and avoid blocking the event loop.
    Configuration may alias existing handlers without recompilation; adding Python
    implementations remains an application code change (or use an external MCP server).
    Runtime replaces the empty startup file scope with the current Run's allowlist.
    """
    return {"parse_pdf": pdf_handler(references if references is not None else FileReferences([]))}
