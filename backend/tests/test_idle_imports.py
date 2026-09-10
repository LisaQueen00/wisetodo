"""Cold idle startup must not import the graph runtime or create a model client."""

import subprocess
import sys


def test_main_import_defers_langgraph():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import wisetodo.main; assert 'langgraph.graph' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
