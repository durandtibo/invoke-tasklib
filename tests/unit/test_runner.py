from __future__ import annotations

import sys
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit

from invoke_tasklib.runner import _split, build_command, check_program, python_executable, run

#######################################
#     Tests for python_executable     #
#######################################


def test_python_executable_returns_running_interpreter() -> None:
    assert python_executable() == sys.executable


def test_python_executable_quotes_path_with_space(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/my env/bin/python")
    assert python_executable() == "'/my env/bin/python'"


#########################
#     Tests for run     #
#########################


def _context(run_config: dict | None = None) -> MockContext:
    return MockContext(config=Config(overrides={"run": run_config or {}}), run=True)


def _run_mock(c: MockContext) -> Mock:
    assert isinstance(c.run, Mock)
    return c.run


def test_run_passes_the_command() -> None:
    c = _context()
    run(c, "ls -l")
    assert _run_mock(c).call_args.args == ("ls -l",)


def test_run_echoes_the_command_by_default() -> None:
    c = _context()
    run(c, "ls")
    assert _run_mock(c).call_args.kwargs["echo"] is True


def test_run_explicit_echo_wins() -> None:
    c = _context()
    run(c, "ls", echo=False)
    assert _run_mock(c).call_args.kwargs["echo"] is False


def test_run_uses_pty_on_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    c = _context()
    run(c, "ls")
    assert _run_mock(c).call_args.kwargs["pty"] is True


def test_run_does_not_use_pty_without_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    c = _context()
    run(c, "ls")
    assert _run_mock(c).call_args.kwargs["pty"] is False


def test_run_uses_pty_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    c = _context({"pty": True})
    run(c, "ls")
    assert _run_mock(c).call_args.kwargs["pty"] is True


def test_run_explicit_pty_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    c = _context()
    run(c, "ls", pty=False)
    assert _run_mock(c).call_args.kwargs["pty"] is False


def test_run_forwards_extra_arguments() -> None:
    c = _context()
    run(c, "ls", warn=True, env={"A": "1"})
    kwargs = _run_mock(c).call_args.kwargs
    assert (kwargs["warn"], kwargs["env"]) == (True, {"A": "1"})


def test_run_returns_the_result_of_the_context() -> None:
    c = _context()
    assert run(c, "ls").command == "ls"


###################################
#     Tests for check_program     #
###################################


def test_check_program_accepts_a_program_on_the_path() -> None:
    assert check_program("ruff check .") is None


def test_check_program_missing_program_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    with pytest.raises(Exit, match=r"'ruff' was not found on the PATH.*invoke env\.install"):
        check_program("ruff check .")


def test_check_program_missing_program_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    with pytest.raises(Exit) as excinfo:
        check_program("ruff check .")
    assert excinfo.value.code == 127


@pytest.mark.parametrize("command", ["find . -name x", "command -v python"])
def test_check_program_skips_unchecked_programs(
    command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    assert check_program(command) is None


def test_check_program_skips_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    assert check_program("/usr/bin/python -m pytest") is None


def test_check_program_skips_empty_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    assert check_program("") is None


def test_check_program_quoted_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    assert check_program("'/path with space/python' -m pytest") is None


def test_run_missing_program_does_not_run_the_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    c = _context()
    with pytest.raises(Exit, match=r"'ruff' was not found"):
        run(c, "ruff check .")
    assert not _run_mock(c).called


###################################
#     Tests for build_command     #
###################################


def test_build_command_uses_default_paths() -> None:
    assert build_command("ruff check", default_paths=["."]) == "ruff check ."


def test_build_command_without_paths_has_only_the_program() -> None:
    assert build_command("ty check") == "ty check"


def test_build_command_adds_args_before_paths() -> None:
    assert build_command("ruff check", args="--select E", default_paths=["."]) == (
        "ruff check --select E ."
    )


def test_build_command_paths_replace_default_paths() -> None:
    assert build_command("ruff check", paths="a.py b.py", default_paths=["."]) == (
        "ruff check a.py b.py"
    )


def test_build_command_quotes_args_with_spaces() -> None:
    assert build_command("pytest", args='-k "a or b"') == "pytest -k 'a or b'"


def test_build_command_quotes_paths_with_spaces() -> None:
    assert build_command("ruff check", paths="'my dir/a.py'") == "ruff check 'my dir/a.py'"


def test_build_command_quotes_shell_metacharacters() -> None:
    assert build_command("ruff check", args="--x ';rm -rf /'") == "ruff check --x ';rm -rf /'"


def test_build_command_does_not_quote_the_program() -> None:
    assert build_command("uv run pip-audit") == "uv run pip-audit"


def test_build_command_unclosed_quote_exits() -> None:
    with pytest.raises(Exit, match=r"Cannot parse the value of --args"):
        build_command("pytest", args="-k 'a")


def test_build_command_unclosed_quote_in_paths_exits() -> None:
    with pytest.raises(Exit, match=r"Cannot parse the value of --paths"):
        build_command("pytest", paths="'a")


##############################
#     Tests for _split     #
##############################


def test_split_none() -> None:
    assert _split(None, "--args") == []


def test_split_empty_string() -> None:
    assert _split("", "--args") == []


def test_split_keeps_quoted_words_together() -> None:
    assert _split("-k 'a b' -x", "--args") == ["-k", "a b", "-x"]


def test_split_unclosed_quote_exit_code() -> None:
    with pytest.raises(Exit) as excinfo:
        _split("'a", "--args")
    assert excinfo.value.code == 2
