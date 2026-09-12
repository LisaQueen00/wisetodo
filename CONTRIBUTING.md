# Contributing

WiseTodo is currently a test-stage project. Discuss behavior changes before implementation, especially model costs, filesystem permissions and desktop interactions.

## Setup and checks

Use the project-local `.venv` with Python 3.12 and the native platform prerequisites in [building.md](docs/building.md). Install frontend dependencies with `pnpm install --frozen-lockfile`.

```text
python -m pip install -e "./backend[dev]"
python -m pytest backend/tests -q
python -m ruff check backend scripts
python -m mypy --config-file backend/pyproject.toml backend/wisetodo
pnpm test
pnpm lint
pnpm build
cargo test --locked --manifest-path src-tauri/Cargo.toml
```

Run Python commands using `.venv/Scripts/python.exe` on Windows or `.venv/bin/python` on macOS/Linux. Tests should use temporary profiles and mocked model/network responses. Never automatically spend real-model tokens or alter a user's actual database and credentials.

## Pull requests

- Keep changes scoped and include regression tests; preserve v1/v2 theme and existing user configuration compatibility.
- Document public behavior and known limitations. Do not equate mocked tests with desktop visual or real-model acceptance.
- Do not commit `.local`, build output, virtual environments, databases, logs containing personal content or credentials.
- Run `node scripts/build_theme_schema.mjs` after changing theme mappings and include the updated generated schema.
- Keep version manifests consistent; do not create tags or publish artifacts without maintainer approval.

There is currently no selected project LICENSE. This document does not grant a software license or replace license selection and third-party notice review before redistribution.
