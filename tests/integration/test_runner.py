from __future__ import annotations

import shlex
import sys

import pytest
from invoke.exceptions import Exit

from invoke_tasklib.runner import check_program


def test_check_program_missing_program_of_a_pipeline_exits_with_its_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    with pytest.raises(Exit, match=r"'no-such-shellcheck' was not found on the PATH"):
        check_program("find . -name '*.sh' -print0 | xargs -0 -r no-such-shellcheck --")


def test_check_program_missing_module_of_the_running_interpreter_exits() -> None:
    with pytest.raises(Exit, match=r"The Python module 'no_such_module_xyz' is not installed"):
        check_program(f"{shlex.quote(sys.executable)} -m no_such_module_xyz")
