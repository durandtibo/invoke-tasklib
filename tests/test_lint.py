from __future__ import annotations

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import lint


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    return [call.args[0] for call in c.run.call_args_list]


def test_check_lint() -> None:
    c = _context()
    lint.check_lint(c)
    assert "ruff check --output-format=github ." in _commands(c)


def test_check_types() -> None:
    c = _context({"package": {"name": "mypkg"}})
    lint.check_types(c)
    assert "pyright --verifytypes mypkg --ignoreexternal" in _commands(c)
