"""Run-bound PDF tool with cancellable subprocess extraction."""

import asyncio
import json
import subprocess
import sys
from contextlib import suppress

from pydantic import JsonValue, TypeAdapter

from wisetodo.files.references import FileReferences
from wisetodo.tools.transport import LocalHandler, ToolTransportError


def pdf_handler(references: FileReferences) -> LocalHandler:
    async def parse_pdf(arguments: dict[str, JsonValue]) -> JsonValue:
        reference = arguments.get("file_ref")
        if set(arguments) != {"file_ref"} or not isinstance(reference, str):
            raise ToolTransportError("invalid_tool_arguments")
        path = references.resolve(reference)
        if path.suffix.lower() != ".pdf":
            raise ToolTransportError("invalid_tool_arguments")
        command = (
            [sys.executable, "--pdf-worker"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "wisetodo.files.pdf_worker"]
        )
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        try:
            async with asyncio.timeout(25):
                assert process.stdin is not None and process.stdout is not None
                process.stdin.write(json.dumps(str(path)).encode("utf-8"))
                await process.stdin.drain()
                process.stdin.close()
                output = bytearray()
                while chunk := await process.stdout.read(8192):
                    output.extend(chunk)
                    if len(output) > 100_000:
                        raise ToolTransportError("result_too_large")
                if await process.wait() != 0:
                    raise ToolTransportError("pdf_worker_failed")
                return TypeAdapter(JsonValue).validate_json(bytes(output))
        finally:
            if process.returncode is None:
                with suppress(ProcessLookupError):
                    process.kill()
            await process.wait()

    return parse_pdf
