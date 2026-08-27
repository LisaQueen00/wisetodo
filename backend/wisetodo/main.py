from __future__ import annotations

import asyncio

from wisetodo.ipc.server import run_stdio_server


def main() -> None:
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
