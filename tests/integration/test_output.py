from __future__ import annotations

import os
import subprocess
import sys


def test_say_does_not_crash_on_ascii_terminal() -> None:
    code = (
        "from invoke.config import Config\n"
        "from invoke.context import Context\n"
        "from invoke_tasklib.output import say\n"
        "say(Context(config=Config()), '\\U0001f9f9 clean')\n"
    )
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "ascii"},
    )
    assert (proc.returncode, proc.stdout) == (0, "? clean\n")
