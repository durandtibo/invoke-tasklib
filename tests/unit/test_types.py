from __future__ import annotations

from unittest.mock import Mock

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import types


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


def test_check() -> None:
    c = _context({"package": {"name": "mypkg"}})
    types.check(c)
    assert _commands(c) == ["ty check"]


def test_check_complete() -> None:
    c = _context({"package": {"name": "mypkg"}})
    types.check(c, complete=True)
    assert _commands(c) == ["ty check", "pyright"]


def test_check_args() -> None:
    c = _context()
    types.check(c, args="--python-version 3.12")
    assert _commands(c) == ["ty check --python-version 3.12"]


def test_check_paths() -> None:
    c = _context()
    types.check(c, paths="src/a.py")
    assert _commands(c) == ["ty check src/a.py"]


def test_check_complete_passes_paths_but_not_args_to_pyright() -> None:
    c = _context()
    types.check(c, complete=True, args="--python-version 3.12", paths="src/a.py")
    assert _commands(c) == ["ty check --python-version 3.12 src/a.py", "pyright src/a.py"]
