from __future__ import annotations

import subprocess
import sys

import pytest
from invoke.exceptions import Exit

from invoke_tasklib.tools import check_program


def test_check_program_missing_program_exits_with_its_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    with pytest.raises(Exit, match=r"'no-such-shellcheck' was not found on the PATH"):
        check_program(["no-such-shellcheck", "--version"])


def test_check_program_missing_module_of_the_running_interpreter_exits() -> None:
    with pytest.raises(Exit, match=r"The Python module 'no_such_module_xyz' is not installed"):
        check_program([sys.executable, "-m", "no_such_module_xyz"])


def test_check_program_accepts_a_real_program(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert check_program(["ls", "-l"]) is None


def test_check_program_looks_up_a_variable_assignment_as_a_program(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    with pytest.raises(Exit, match=r"'FOO=1' was not found on the PATH"):
        check_program(["FOO=1", "ls"])


def test_run_gives_the_words_to_the_shell_unchanged() -> None:
    code = (
        "from invoke.config import Config\n"
        "from invoke.context import Context\n"
        "from invoke_tasklib.runner import run\n"
        "words = ['echo', 'a b;$HOME', '*', '~', \"it's\"]\n"
        "run(Context(config=Config()), words, echo=False, pty=False)\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout == "a b;$HOME * ~ it's\n"


def test_run_rejects_a_string() -> None:
    code = (
        "from invoke.config import Config\n"
        "from invoke.context import Context\n"
        "from invoke_tasklib.runner import run\n"
        "run(Context(config=Config()), 'echo hello', echo=False, pty=False)\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.stderr.splitlines()[-1].startswith("TypeError: pass the command as a list")


def test_check_program_accepts_the_installed_pytest_plugins() -> None:
    command = [sys.executable, "-m", "pytest", "--xdoctest", "--timeout", "5", "--cov=x", "tests"]
    assert check_program(command) is None
