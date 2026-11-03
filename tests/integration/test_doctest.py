from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).parents[2] / "src"


def test_docstring_examples_pass() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "--xdoctest", "-q", "-p", "no:cacheprovider", str(SRC)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout
