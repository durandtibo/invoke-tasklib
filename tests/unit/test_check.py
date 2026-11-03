from __future__ import annotations

import sys
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit

from invoke_tasklib import check


@pytest.fixture(autouse=True)
def _fixed_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")


def _context() -> MockContext:
    overrides = {"tasklib": {"package": {"name": "mypkg"}}}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


##########################
#     Tests for all_     #
##########################


def test_all_runs_the_checks_in_order() -> None:
    c = _context()
    check.all_(c)
    assert _commands(c)[:4] == [
        "ruff format --check .",
        "docformatter --config ./pyproject.toml --check src/mypkg",
        "ruff check .",
        "ty check",
    ]


def test_all_ends_with_the_unit_tests() -> None:
    c = _context()
    check.all_(c)
    assert _commands(c)[-1] == "/venv/bin/python -m pytest --xdoctest --timeout 10 tests/unit"


def test_all_does_not_modify_files() -> None:
    c = _context()
    check.all_(c)
    assert not [cmd for cmd in _commands(c) if "--fix" in cmd or "--in-place" in cmd]


def test_all_stops_at_the_first_failure() -> None:
    c = _context()
    c.run = Mock(side_effect=Exit("failed"))
    with pytest.raises(Exit, match=r"failed"):
        check.all_(c)


def test_all_runs_nothing_after_the_first_failure() -> None:
    c = _context()
    run = Mock(side_effect=Exit("failed"))
    c.run = run
    with pytest.raises(Exit, match=r"failed"):
        check.all_(c)
    assert run.call_count == 1
