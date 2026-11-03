from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit, UnexpectedExit
from invoke.runners import Result

from invoke_tasklib import check
from invoke_tasklib.config import CHECK_STEPS

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _fixed_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")


@pytest.fixture(autouse=True)
def _package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Make ``mypkg`` findable, for the static import check."""
    (tmp_path / "mypkg").mkdir()
    (tmp_path / "mypkg" / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))


def _context(check_config: dict | None = None) -> MockContext:
    tasklib = {"package": {"name": "mypkg"}}
    if check_config is not None:
        tasklib["check"] = check_config
    return MockContext(config=Config(overrides={"tasklib": tasklib}), run=True)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


def _failing(c: MockContext, *failing: str) -> None:
    r"""Make the commands starting with a prefix of ``failing`` fail."""

    def run(cmd: str, **_kwargs: object) -> Result:
        result = Result(exited=1, command=cmd)
        if any(cmd.startswith(prefix) for prefix in failing):
            raise UnexpectedExit(result)
        return result

    c.run = Mock(side_effect=run)


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


def test_all_runs_the_configured_steps() -> None:
    c = _context({"tasks": ["lint", "format-python"]})
    check.all_(c)
    assert _commands(c) == ["ruff check .", "ruff format --check ."]


def test_all_runs_the_optional_steps_when_configured() -> None:
    c = _context({"tasks": "docs,audit"})
    check.all_(c)
    assert _commands(c)[0] == "mkdocs build --strict --config-file docs/mkdocs.yml"


def test_all_only_replaces_the_configured_steps() -> None:
    c = _context()
    check.all_(c, only="types")
    assert _commands(c) == ["ty check"]


def test_all_only_keeps_the_order_given() -> None:
    c = _context()
    check.all_(c, only="types,lint")
    assert _commands(c) == ["ty check", "ruff check ."]


def test_all_skip_removes_steps() -> None:
    c = _context({"tasks": "lint,types,format-python"})
    check.all_(c, skip="types")
    assert _commands(c) == ["ruff check .", "ruff format --check ."]


def test_all_skip_is_applied_to_only() -> None:
    c = _context()
    check.all_(c, only="lint,types", skip="lint")
    assert _commands(c) == ["ty check"]


def test_all_rejects_an_unknown_only_step() -> None:
    with pytest.raises(Exit, match=r"Unknown step \['lnt'\] in --only"):
        check.all_(_context(), only="lnt")


def test_all_rejects_an_unknown_skip_step() -> None:
    with pytest.raises(Exit, match=r"Unknown step \['nope'\] in --skip"):
        check.all_(_context(), skip="nope")


def test_all_with_unknown_step_runs_nothing() -> None:
    c = _context()
    with pytest.raises(Exit, match=r"Unknown step"):
        check.all_(c, skip="nope")
    assert _commands(c) == []


def test_all_reports_an_invalid_config() -> None:
    with pytest.raises(Exit, match=r"Unknown check step"):
        check.all_(_context({"tasks": "nope"}))


def test_all_keep_going_runs_every_step_after_a_failure() -> None:
    c = _context({"tasks": "format-python,lint,types"})
    _failing(c, "ruff format")
    with pytest.raises(Exit, match=r"1 of 3 check\(s\) failed: format-python"):
        check.all_(c, keep_going=True)
    assert _commands(c) == ["ruff format --check .", "ruff check .", "ty check"]


def test_all_keep_going_lists_all_the_failed_steps() -> None:
    c = _context({"tasks": "format-python,lint,types"})
    _failing(c, "ruff format", "ty")
    with pytest.raises(Exit, match=r"2 of 3 check\(s\) failed: format-python, types"):
        check.all_(c, keep_going=True)


def test_all_keep_going_exits_with_code_1() -> None:
    c = _context({"tasks": "lint"})
    _failing(c, "ruff")
    with pytest.raises(Exit) as info:
        check.all_(c, keep_going=True)
    assert info.value.code == 1


def test_all_keep_going_passes_when_no_step_fails() -> None:
    c = _context({"tasks": "lint,types"})
    check.all_(c, keep_going=True)
    assert _commands(c) == ["ruff check .", "ty check"]


def test_all_keep_going_catches_a_missing_program() -> None:
    c = _context({"tasks": "lint,types"})
    c.run = Mock(side_effect=[Exit("ruff not found"), Result()])
    with pytest.raises(Exit, match=r"1 of 2 check\(s\) failed: lint"):
        check.all_(c, keep_going=True)


def test_all_keep_going_names_the_failed_step(capsys: pytest.CaptureFixture[str]) -> None:
    c = _context({"tasks": "lint"})
    _failing(c, "ruff")
    with pytest.raises(Exit, match=r"failed"):
        check.all_(c, keep_going=True)
    assert "❌ Step failed: lint" in capsys.readouterr().out


##################################
#     Tests for _parse_steps     #
##################################


def test_parse_steps_none_is_empty() -> None:
    assert check._parse_steps("--only", None) == []


def test_parse_steps_strips_and_removes_duplicates() -> None:
    assert check._parse_steps("--only", " lint , unit,lint") == ["lint", "unit"]


def test_parse_steps_rejects_an_unknown_step() -> None:
    with pytest.raises(Exit, match=r"Unknown step \['x'\] in --skip") as info:
        check._parse_steps("--skip", "lint,x")
    assert info.value.code == 2


###################################
#     Tests for _select_steps     #
###################################


def test_select_steps_uses_the_configured_steps() -> None:
    assert check._select_steps(("lint", "unit"), [], []) == ["lint", "unit"]


def test_select_steps_only_wins_over_the_configured_steps() -> None:
    assert check._select_steps(("lint", "unit"), ["docs"], []) == ["docs"]


def test_select_steps_skip_removes_a_step() -> None:
    assert check._select_steps(("lint", "unit"), [], ["lint"]) == ["unit"]


def test_select_steps_does_not_mutate_its_inputs() -> None:
    only = ["lint", "unit"]
    check._select_steps((), only, ["lint"])
    assert only == ["lint", "unit"]


###############################
#     Tests for _run_step     #
###############################


def test_run_step_passes() -> None:
    assert check._run_step(_context(), "types") is None


def test_run_step_returns_the_failure_message() -> None:
    c = _context()
    c.run = Mock(side_effect=Exit("boom"))
    assert check._run_step(c, "types") == "boom"


def test_run_step_returns_a_message_for_a_failed_command() -> None:
    c = _context()
    _failing(c, "ty")
    assert check._run_step(c, "types") is not None


def test_run_step_does_not_catch_other_exceptions() -> None:
    c = _context()
    c.run = Mock(side_effect=KeyboardInterrupt("interrupted"))
    with pytest.raises(KeyboardInterrupt, match=r"interrupted"):
        check._run_step(c, "types")


###########################
#     Tests for STEPS     #
###########################


def test_steps_are_the_valid_steps_of_the_config() -> None:
    assert tuple(check.STEPS) == CHECK_STEPS
