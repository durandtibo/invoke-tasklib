from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit, UnexpectedExit
from invoke.runners import Result

from invoke_tasklib import check, env
from invoke_tasklib.config import CHECK_STEPS, load_config
from tests.helpers import commands, make_context

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from invoke_tasklib.config import TasklibConfig


@pytest.fixture(autouse=True)
def _fixed_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")


@pytest.fixture(autouse=True)
def _tools_found(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Make every tool available, whatever is installed."""
    monkeypatch.setattr(check, "find_tool", lambda name, **_kwargs: f"/found/{name}")


def _available(*names: str) -> Callable[..., str | None]:
    r"""Return a ``find_tool`` that only finds the tools ``names``."""
    return lambda name, **_kwargs: f"/found/{name}" if name in names else None


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
    assert commands(c)[:4] == [
        "ruff format --check .",
        "docformatter --config ./pyproject.toml --check src/mypkg",
        "ruff check .",
        "ty check",
    ]


def test_all_ends_with_the_unit_tests() -> None:
    c = _context()
    check.all_(c)
    assert commands(c)[-1] == "/venv/bin/python -m pytest --xdoctest --timeout 10 tests/unit"


def test_all_does_not_modify_files() -> None:
    c = _context()
    check.all_(c)
    assert not [cmd for cmd in commands(c) if "--fix" in cmd or "--in-place" in cmd]


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
    assert commands(c) == ["ruff check .", "ruff format --check ."]


def test_all_runs_the_optional_steps_when_configured() -> None:
    c = _context({"tasks": "docs,audit"})
    check.all_(c)
    assert commands(c)[0] == "mkdocs build --strict --config-file docs/mkdocs.yml"


def test_all_only_replaces_the_configured_steps() -> None:
    c = _context()
    check.all_(c, only="types")
    assert commands(c) == ["ty check"]


def test_all_only_keeps_the_order_given() -> None:
    c = _context()
    check.all_(c, only="types,lint")
    assert commands(c) == ["ty check", "ruff check ."]


def test_all_skip_removes_steps() -> None:
    c = _context({"tasks": "lint,types,format-python"})
    check.all_(c, skip="types")
    assert commands(c) == ["ruff check .", "ruff format --check ."]


def test_all_skip_is_applied_to_only() -> None:
    c = _context()
    check.all_(c, only="lint,types", skip="lint")
    assert commands(c) == ["ty check"]


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
    assert commands(c) == []


def test_all_reports_an_invalid_config() -> None:
    with pytest.raises(Exit, match=r"Unknown check step"):
        check.all_(_context({"tasks": "nope"}))


def test_all_keep_going_runs_every_step_after_a_failure() -> None:
    c = _context({"tasks": "format-python,lint,types"})
    _failing(c, "ruff format")
    with pytest.raises(Exit, match=r"1 of 3 check\(s\) failed: format-python"):
        check.all_(c, keep_going=True)
    assert commands(c) == ["ruff format --check .", "ruff check .", "ty check"]


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
    assert commands(c) == ["ruff check .", "ty check"]


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


def test_all_keep_going_prints_the_reason_of_the_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    c = _context({"tasks": "lint"})
    c.run = Mock(side_effect=Exit("'ruff' was not found on the PATH."))
    with pytest.raises(Exit, match=r"failed"):
        check.all_(c, keep_going=True)
    assert "   'ruff' was not found on the PATH.\n" in capsys.readouterr().out


def test_all_keep_going_prints_the_reason_after_the_step_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    c = _context({"tasks": "lint"})
    c.run = Mock(side_effect=Exit("boom"))
    with pytest.raises(Exit, match=r"failed"):
        check.all_(c, keep_going=True)
    assert "❌ Step failed: lint\n   boom\n" in capsys.readouterr().out


def test_all_keep_going_prints_the_exit_code_of_a_failed_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    c = _context({"tasks": "types"})
    _failing(c, "ty")
    with pytest.raises(Exit, match=r"failed"):
        check.all_(c, keep_going=True)
    assert "   The command 'ty check' exited with code 1\n" in capsys.readouterr().out


def test_all_missing_tool_stops_before_any_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check, "find_tool", _available("ruff"))
    c = _context({"tasks": "format-python,lint,types"})
    with pytest.raises(Exit, match=r"1 tool\(s\) missing for the selected steps"):
        check.all_(c)
    assert commands(c) == []


def test_all_missing_tool_exits_with_code_127(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check, "find_tool", _available())
    with pytest.raises(Exit, match=r"missing") as info:
        check.all_(_context({"tasks": "lint"}))
    assert info.value.code == 127


def test_all_missing_tools_are_all_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check, "find_tool", _available("ruff"))
    c = _context({"tasks": "format-python,format-docstrings,types,spelling"})
    with pytest.raises(Exit) as info:
        check.all_(c)
    assert str(info.value) == (
        "3 tool(s) missing for the selected steps:\n"
        "  'docformatter' was not found on the PATH. Install it with the 'dev' group: "
        "`uv sync --group dev`. (needed by: format-docstrings)\n"
        "  'ty' was not found on the PATH. Install it with the 'dev' group: "
        "`uv sync --group dev`. (needed by: types)\n"
        "  'codespell' was not found on the PATH. Add codespell to the dependencies of the "
        "project, e.g. `uv add --dev codespell`. (needed by: spelling)"
    )


def test_all_missing_tool_shared_by_steps_is_listed_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check, "find_tool", _available())
    with pytest.raises(
        Exit, match=r"1 tool\(s\) missing .*\n  'ruff' .*\(needed by: format-python, lint\)"
    ):
        check.all_(_context({"tasks": "format-python,lint"}))


def test_all_does_not_look_up_the_tools_of_skipped_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check, "find_tool", _available("ruff"))
    c = _context({"tasks": "lint,types"})
    check.all_(c, skip="types")
    assert commands(c) == ["ruff check ."]


def test_all_missing_module_names_the_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check, "find_tool", _available())
    with pytest.raises(
        Exit, match=r"The Python module 'pytest' is not installed .*\(needed by: unit\)"
    ):
        check.all_(_context({"tasks": "unit"}))


def test_all_keep_going_does_not_run_a_step_with_a_missing_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(check, "find_tool", _available("ruff"))
    c = _context({"tasks": "lint,types"})
    with pytest.raises(Exit, match=r"1 of 2 check\(s\) failed: types"):
        check.all_(c, keep_going=True)
    assert commands(c) == ["ruff check ."]


def test_all_keep_going_prints_the_missing_tool_of_a_step(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check, "find_tool", _available())
    with pytest.raises(Exit, match=r"failed"):
        check.all_(_context({"tasks": "types"}), keep_going=True)
    assert capsys.readouterr().out == (
        "🔎 Running all the checks...\n"
        "❌ Step failed: types\n"
        "   'ty' was not found on the PATH. Install it with the 'dev' group: "
        "`uv sync --group dev`.\n"
    )


def test_all_keep_going_lists_every_missing_tool_of_a_step(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check, "find_tool", _available())
    with pytest.raises(Exit, match=r"failed"):
        check.all_(_context({"tasks": "audit"}), keep_going=True)
    assert capsys.readouterr().out.count("was not found on the PATH") == 2


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


def test_run_step_returns_the_command_and_code_of_a_failed_command() -> None:
    c = _context()
    _failing(c, "ty")
    assert check._run_step(c, "types") == "The command 'ty check' exited with code 1"


def test_run_step_names_the_exception_when_the_message_is_empty() -> None:
    c = _context()
    c.run = Mock(side_effect=Exit())
    assert check._run_step(c, "types") == "Exit"


def test_run_step_does_not_catch_other_exceptions() -> None:
    c = _context()
    c.run = Mock(side_effect=KeyboardInterrupt("interrupted"))
    with pytest.raises(KeyboardInterrupt, match=r"interrupted"):
        check._run_step(c, "types")


###################################
#     Tests for _missing_tools    #
###################################


def _cfg(xdoctest: bool = True) -> TasklibConfig:
    return load_config(make_context({"package": {"name": "mypkg"}, "test": {"xdoctest": xdoctest}}))


def test_missing_tools_none_missing() -> None:
    assert check._missing_tools("lint", _cfg()) == []


def test_missing_tools_step_without_tools() -> None:
    assert check._missing_tools("imports", _cfg()) == []


def test_missing_tools_program(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check, "find_tool", _available())
    assert check._missing_tools("types", _cfg()) == [
        (
            "ty",
            "'ty' was not found on the PATH. Install it with the 'dev' group: `uv sync --group dev`.",
        )
    ]


def test_missing_tools_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check, "find_tool", _available("pytest_timeout", "xdoctest"))
    assert check._missing_tools("unit", _cfg()) == [
        (
            "pytest",
            (
                "The Python module 'pytest' is not installed for /venv/bin/python. "
                "Install it with the 'dev' group: `uv sync --group dev`."
            ),
        )
    ]


def test_missing_tools_programs_come_before_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check, "find_tool", _available())
    names = [name for name, _ in check._missing_tools("audit", _cfg())]
    assert names == ["uv", "uvx"]


def test_missing_tools_unit_needs_xdoctest_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(check, "find_tool", _available("pytest", "pytest_timeout"))
    assert [name for name, _ in check._missing_tools("unit", _cfg(xdoctest=True))] == ["xdoctest"]


def test_missing_tools_unit_does_not_need_xdoctest_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(check, "find_tool", _available("pytest", "pytest_timeout"))
    assert check._missing_tools("unit", _cfg(xdoctest=False)) == []


def test_missing_tools_looks_modules_up_as_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    def find(name: str, *, module: bool = False) -> str:
        calls.append((name, module))
        return name

    monkeypatch.setattr(check, "find_tool", find)
    check._missing_tools("doctest", _cfg())
    assert calls == [("pytest", True), ("xdoctest", True)]


########################################
#     Tests for _preflight_message     #
########################################


def test_preflight_message_one_tool() -> None:
    assert check._preflight_message({"lint": [("ruff", "Install it.")]}) == (
        "1 tool(s) missing for the selected steps:\n  Install it. (needed by: lint)"
    )


def test_preflight_message_merges_a_tool_of_several_steps() -> None:
    blocked = {"lint": [("ruff", "Install it.")], "format-python": [("ruff", "Install it.")]}
    assert check._preflight_message(blocked) == (
        "1 tool(s) missing for the selected steps:\n  Install it. (needed by: lint, format-python)"
    )


def test_preflight_message_does_not_mutate_its_input() -> None:
    blocked = {"lint": [("ruff", "Install it.")]}
    check._preflight_message(blocked)
    assert blocked == {"lint": [("ruff", "Install it.")]}


###########################
#     Tests for STEPS     #
###########################


def test_steps_are_the_valid_steps_of_the_config() -> None:
    assert tuple(check.STEPS) == CHECK_STEPS


#######################################
#     Tests for PROGRAMS, MODULES     #
#######################################


def test_programs_have_an_entry_for_every_step() -> None:
    assert tuple(check.PROGRAMS) == CHECK_STEPS


def test_modules_have_an_entry_for_every_step() -> None:
    assert tuple(check.MODULES) == CHECK_STEPS


def test_programs_are_checked_by_env_check_tools() -> None:
    assert {name for names in check.PROGRAMS.values() for name in names} <= set(env.TOOL_PROGRAMS)


def test_modules_are_checked_by_env_check_tools() -> None:
    assert {name for names in check.MODULES.values() for name in names} <= set(env.TOOL_MODULES)
