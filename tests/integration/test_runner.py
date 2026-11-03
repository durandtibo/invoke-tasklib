from __future__ import annotations

import shlex
import sys

import pytest
from invoke.config import Config
from invoke.context import Context
from invoke.exceptions import Exit

from invoke_tasklib.runner import check_program, run


def test_check_program_missing_program_of_a_pipeline_exits_with_its_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    with pytest.raises(Exit, match=r"'no-such-shellcheck' was not found on the PATH"):
        check_program("find . -name '*.sh' -print0 | xargs -0 -r no-such-shellcheck --")


def test_check_program_missing_module_of_the_running_interpreter_exits() -> None:
    with pytest.raises(Exit, match=r"The Python module 'no_such_module_xyz' is not installed"):
        check_program(f"{shlex.quote(sys.executable)} -m no_such_module_xyz")


def test_check_program_accepts_an_assignment_before_a_real_program(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert check_program("FOO=1 ls") is None


def test_check_program_accepts_a_builtin_without_an_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    assert check_program("cd . && export FOO=1") is None


def test_run_executes_a_command_with_an_assignment_and_a_builtin(
    capfd: pytest.CaptureFixture[str],
) -> None:
    run(
        Context(config=Config()),
        "FOO=hello; cd . && echo $FOO",
        echo=False,
        pty=False,
        in_stream=False,
    )
    assert capfd.readouterr().out == "hello\n"
