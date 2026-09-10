import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "response",
    [
        {"requestId": "smoke", "result": {"todos": []}},
        {"requestId": "wrong", "result": {"todos": []}},
        {"requestId": "smoke", "error": {"code": "INTERNAL_ERROR"}},
        {"requestId": "smoke", "result": {}},
    ],
)
def test_frozen_smoke_requires_valid_ipc_on_both_starts(tmp_path, monkeypatch, response):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        assert kwargs["creationflags"] == (
            subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        assert Path(args[-1]).is_absolute()
        assert json.loads(kwargs["input"])["method"] == "todos.list"
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(response))

    binary = tmp_path / "binary"
    binary.touch()
    monkeypatch.setattr(sys, "argv", ["smoke_sidecar.py", str(binary)])
    monkeypatch.setattr(subprocess, "run", run)
    module = runpy.run_path(str(ROOT / "scripts" / "smoke_sidecar.py"))
    if response == {"requestId": "smoke", "result": {"todos": []}}:
        module["main"]()
        assert len(calls) == 2
        assert calls[0][0] == calls[1][0]
    else:
        with pytest.raises(RuntimeError):
            module["main"]()


def test_build_matrix_and_release_only_sidecar_configuration():
    workflow = yaml.safe_load((ROOT / ".github/workflows/build.yml").read_text())
    rows = workflow["jobs"]["build"]["strategy"]["matrix"]["include"]
    assert {row["bundle"] for row in rows} == {"nsis", "deb", "dmg"}
    assert workflow["permissions"] == {"contents": "read"}
    normal = json.loads((ROOT / "src-tauri/tauri.conf.json").read_text())
    release = json.loads((ROOT / "src-tauri/tauri.bundle.conf.json").read_text())
    assert "externalBin" not in normal["bundle"]
    assert release["bundle"]["externalBin"] == ["binaries/wisetodo-sidecar"]
