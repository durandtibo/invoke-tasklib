from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib.runner import python_executable, run

if TYPE_CHECKING:
    import pytest

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
