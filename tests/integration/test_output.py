from __future__ import annotations

import os
import subprocess
import sys

_CODE = (
    "from invoke.config import Config\n"
    "from invoke.context import Context\n"
    "from invoke_tasklib.output import say\n"
    "say(Context(config=Config()), '\\u2705 \\U0001f9f9 clean')\n"
)


def test_say_does_not_crash_on_ascii_terminal() -> None:
    code = _CODE
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "ascii"},
    )
    assert (proc.returncode, proc.stdout) == (0, "[ok] clean\n")


def test_say_gives_ascii_output_on_a_utf8_terminal_when_asked() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _CODE],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "INVOKE_TASKLIB_ASCII": "1"},
    )
    assert (proc.returncode, proc.stdout) == (0, "[ok] clean\n")
