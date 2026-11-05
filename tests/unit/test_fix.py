from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from invoke.exceptions import Exit

from invoke_tasklib import _steps, fix
from invoke_tasklib.config import FIX_STEPS, get_config
from invoke_tasklib.tools import TOOLS
from tests.helpers import commands, make_context

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture(autouse=True)
def _tools_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", lambda name, **_kwargs: f"/found/{name}")


def _available(*names: str) -> Callable[..., str | None]:
    return lambda name, **_kwargs: f"/found/{name}" if name in names else None


def _context(fix_config: dict | None = None):  # noqa: ANN202
    tasklib: dict = {"package": {"name": "mypkg"}}
    if fix_config is not None:
        tasklib["fix"] = fix_config
    return make_context(tasklib)


def test_all_runs_the_fixers_in_order() -> None:
    c = _context()
    fix.all_(c)
    assert commands(c) == [
        "ruff check --fix .",
        "ruff format .",
        "docformatter --config ./pyproject.toml --in-place src/mypkg",
    ]


def test_all_runs_the_lint_fixes_before_the_formatting() -> None:
    c = _context()
    fix.all_(c)
    assert commands(c)[0].startswith("ruff check --fix")


def test_all_runs_the_configured_steps() -> None:
    c = _context({"tasks": "format-python"})
    fix.all_(c)
    assert commands(c) == ["ruff format ."]


def test_all_only_replaces_the_configured_steps() -> None:
    c = _context()
    fix.all_(c, only="lint")
    assert commands(c) == ["ruff check --fix ."]


def test_all_skip_removes_steps() -> None:
    c = _context()
    fix.all_(c, skip="lint,format-docstrings")
    assert commands(c) == ["ruff format ."]


def test_all_rejects_an_unknown_step() -> None:
    with pytest.raises(Exit, match=r"Unknown step \['types'\] in --only"):
        fix.all_(_context(), only="types")


def test_all_missing_tool_runs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("ruff"))
    c = _context()
    with pytest.raises(Exit, match=r"'docformatter' was not found"):
        fix.all_(c)
    assert commands(c) == []


def test_all_missing_tool_exits_with_code_127(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available())
    with pytest.raises(Exit, match=r"tool\(s\) missing") as info:
        fix.all_(_context())
    assert info.value.code == 127


def test_all_keep_going_skips_the_step_with_a_missing_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("ruff"))
    c = _context()
    with pytest.raises(Exit, match=r"1 of 3 fix\(es\) failed: format-docstrings"):
        fix.all_(c, keep_going=True)
    assert commands(c) == ["ruff check --fix .", "ruff format ."]


def test_all_says_what_it_does(capsys: pytest.CaptureFixture[str]) -> None:
    fix.all_(_context(), only="format-python")
    assert capsys.readouterr().out.splitlines()[0] == "🔧 Running all the fixes..."


def test_all_ends_with_a_done_message(capsys: pytest.CaptureFixture[str]) -> None:
    fix.all_(_context(), only="format-python")
    assert capsys.readouterr().out.splitlines()[-1] == "✅ All fixes applied"


def test_all_reports_an_invalid_config() -> None:
    with pytest.raises(Exit, match=r"tasklib\.package\.name"):
        fix.all_(make_context())


def test_steps_are_the_valid_steps_of_the_config() -> None:
    assert tuple(fix.STEPS) == FIX_STEPS


def test_programs_of_the_steps_are_checked_by_env_check_tools() -> None:
    cfg = get_config(_context())
    programs = {name for step in fix.STEPS.values() for name in step.needs(cfg)[0]}
    assert programs <= {n for n, t in TOOLS.items() if t.kind == "program"}
