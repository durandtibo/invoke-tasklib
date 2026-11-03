from __future__ import annotations

import sys
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.runners import Result

from invoke_tasklib import imports


@pytest.fixture(autouse=True)
def _fixed_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")


def _context(tasklib_config: dict | None = None, run: object = True) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=run)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


_DISCOVER_CMD = "/venv/bin/python -m invoke_tasklib._discover mypkg"


##################################
#     Tests for check_cycles     #
##################################


def test_check_cycles_discovers_then_imports_each_module() -> None:
    c = _context(
        tasklib_config={"package": {"name": "mypkg"}},
        run={
            _DISCOVER_CMD: Result(stdout="mypkg\nmypkg.a\nmypkg.sub\nmypkg.sub.b\n"),
            "/venv/bin/python -c 'import mypkg'": Result(),
            "/venv/bin/python -c 'import mypkg.a'": Result(),
            "/venv/bin/python -c 'import mypkg.sub'": Result(),
            "/venv/bin/python -c 'import mypkg.sub.b'": Result(),
        },
    )
    imports.check_cycles(c)
    assert _commands(c) == [
        _DISCOVER_CMD,
        "/venv/bin/python -c 'import mypkg'",
        "/venv/bin/python -c 'import mypkg.a'",
        "/venv/bin/python -c 'import mypkg.sub'",
        "/venv/bin/python -c 'import mypkg.sub.b'",
    ]


def test_check_cycles_does_not_embed_a_script() -> None:
    c = _context(
        tasklib_config={"package": {"name": "mypkg"}},
        run={_DISCOVER_CMD: Result(stdout="")},
    )
    imports.check_cycles(c)
    assert _commands(c) == [_DISCOVER_CMD]


def test_check_cycles_quotes_package_name() -> None:
    cmd = "/venv/bin/python -m invoke_tasklib._discover 'my pkg'"
    c = _context(
        tasklib_config={"package": {"name": "my pkg"}},
        run={cmd: Result(stdout="")},
    )
    imports.check_cycles(c)
    assert _commands(c) == [cmd]


def test_check_cycles_reports_progress(capsys: pytest.CaptureFixture[str]) -> None:
    c = _context(
        tasklib_config={"package": {"name": "mypkg"}},
        run={
            _DISCOVER_CMD: Result(stdout="mypkg\n"),
            "/venv/bin/python -c 'import mypkg'": Result(),
        },
    )
    imports.check_cycles(c)
    assert capsys.readouterr().out == (
        "🔍 Discovering modules of mypkg...\n"
        "🔍 Checking 1 module(s) for cyclic imports...\n"
        "🔍 Checking: mypkg\n"
        "✅ All 1 module(s) imported without cyclic dependency errors\n"
    )
