import json
import runpy
import subprocess
from pathlib import Path

import pytest

SCRIPT = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/accept_release.py"))


@pytest.mark.parametrize(
    "response",
    [
        {"requestId": "wrong", "result": {}},
        {"requestId": "acceptance", "error": {"code": "FAILED"}},
        {"requestId": "acceptance", "result": None},
    ],
)
def test_acceptance_rejects_invalid_ipc(monkeypatch, tmp_path, response):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 0, stdout=json.dumps(response)),
    )
    with pytest.raises(RuntimeError):
        SCRIPT["request"](tmp_path / "binary", tmp_path, "todos.list", {})


def test_acceptance_request_is_isolated_and_has_timeout(monkeypatch, tmp_path):
    def run(args, **kwargs):
        assert args[-1] == str(tmp_path / "acceptance.db")
        assert kwargs["cwd"] == tmp_path
        assert kwargs["timeout"] == 120
        assert json.loads(kwargs["input"])["method"] == "todos.list"
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps(
                {
                    "requestId": "acceptance",
                    "result": {"todos": []},
                }
            ),
        )

    monkeypatch.setattr(subprocess, "run", run)
    assert SCRIPT["request"](tmp_path / "binary", tmp_path, "todos.list", {}) == {"todos": []}
