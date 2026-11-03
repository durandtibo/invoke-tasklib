from __future__ import annotations

from unittest.mock import Mock

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


def test_check_python() -> None:
    c = _context()
    lint.check_python(c)
    assert _commands(c) == ["ruff check --output-format=github ."]


def test_fix_python() -> None:
    c = _context()
    lint.fix_python(c)
    assert _commands(c) == ["ruff check --fix ."]
