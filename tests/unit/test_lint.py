from __future__ import annotations

from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import lint


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


@pytest.fixture(autouse=True)
def _outside_github_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


def test_check_python() -> None:
    c = _context()
    lint.check_python(c)
    assert _commands(c) == ["ruff check ."]


def test_check_python_uses_github_format_in_github_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    c = _context()
    lint.check_python(c)
    assert _commands(c) == ["ruff check --output-format=github ."]


def test_check_python_explicit_format_wins_in_github_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    c = _context()
    lint.check_python(c, output_format="concise")
    assert _commands(c) == ["ruff check --output-format=concise ."]


def test_check_python_explicit_format() -> None:
    c = _context()
    lint.check_python(c, output_format="full")
    assert _commands(c) == ["ruff check --output-format=full ."]


def test_check_python_ignores_other_github_actions_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    c = _context()
    lint.check_python(c)
    assert _commands(c) == ["ruff check ."]


def test_fix_python() -> None:
    c = _context()
    lint.fix_python(c)
    assert _commands(c) == ["ruff check --fix ."]


def test_check_python_args() -> None:
    c = _context()
    lint.check_python(c, args="--select E")
    assert _commands(c) == ["ruff check --select E ."]


def test_check_python_paths() -> None:
    c = _context()
    lint.check_python(c, paths="a.py b.py")
    assert _commands(c) == ["ruff check a.py b.py"]


def test_check_python_args_and_format_and_paths() -> None:
    c = _context()
    lint.check_python(c, output_format="full", args="--select E", paths="a.py")
    assert _commands(c) == ["ruff check --output-format=full --select E a.py"]


def test_fix_python_args() -> None:
    c = _context()
    lint.fix_python(c, args="--select I")
    assert _commands(c) == ["ruff check --fix --select I ."]


def test_fix_python_paths() -> None:
    c = _context()
    lint.fix_python(c, paths="a.py")
    assert _commands(c) == ["ruff check --fix a.py"]
