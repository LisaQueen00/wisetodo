from __future__ import annotations

import asyncio
import json
import sys
from contextlib import suppress
from typing import Any

from pydantic import TypeAdapter

from wisetodo.ipc.messages import IpcCancel, IpcRequest, IpcResponse

IncomingMessage: TypeAdapter[IpcRequest | IpcCancel] = TypeAdapter(IpcRequest | IpcCancel)


async def dispatch(request: IpcRequest) -> dict[str, Any]:
    if request.method == "health":
        return {"status": "ok"}
    raise ValueError(f"unknown IPC method: {request.method}")


async def run_stdio_server() -> None:
    """Read one JSON request per line and emit one JSON response per line."""
    while line := await asyncio.to_thread(sys.stdin.readline):
        message = IncomingMessage.validate_json(line)
        if isinstance(message, IpcCancel):
            continue

        result = await dispatch(message)
        response = IpcResponse(requestId=message.request_id, result=result)
        print(response.model_dump_json(by_alias=True), flush=True)


if __name__ == "__main__":
    with suppress(EOFError, KeyboardInterrupt, json.JSONDecodeError):
        asyncio.run(run_stdio_server())
