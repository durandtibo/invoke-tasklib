from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.exceptions import Exit, UnexpectedExit
from invoke.runners import Result

from invoke_tasklib import _steps, check
from invoke_tasklib._steps import missing_tools
from invoke_tasklib.config import CHECK_STEPS, get_config, load_config
from invoke_tasklib.tools import TOOLS
from tests.helpers import commands, make_context

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from invoke.context import MockContext

    from invoke_tasklib.config import TasklibConfig


@pytest.fixture(autouse=True)
def _fixed_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")


@pytest.fixture(autouse=True)
def _tools_found(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Make every tool available, whatever is installed."""
    monkeypatch.setattr(_steps, "find_tool", lambda name, **_kwargs: f"/found/{name}")


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
    return make_context(tasklib)


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


def test_all_unit_step_runs_with_coverage_when_check_cov_is_set() -> None:
    c = _context({"tasks": "unit", "cov": True})
    check.all_(c)
    expected = (
        "/venv/bin/python -m pytest --xdoctest --timeout 10 --cov-report html "
        "--cov-report xml --cov-report term --cov=mypkg tests/unit"
    )
    assert commands(c) == [expected]


def test_all_unit_step_enforces_cov_fail_under_when_check_cov_is_set() -> None:
    c = _context({"tasks": "unit", "cov": True})
    c.config.tasklib["test"] = {"cov_fail_under": 90}
    check.all_(c)
    assert "--cov-fail-under=90" in commands(c)[-1]


def test_all_unit_step_does_not_use_coverage_by_default() -> None:
    c = _context({"tasks": "unit"})
    c.config.tasklib["test"] = {"cov_fail_under": 90}
    check.all_(c)
    assert commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 10 tests/unit"]


def test_all_does_not_modify_files() -> None:
    c = _context()
    check.all_(c)
    assert not [cmd for cmd in commands(c) if "--fix" in cmd or "--in-place" in cmd]


def test_all_stops_at_the_first_failure() -> None:
    c = _context()
    c.run = Mock(side_effect=Exit("failed"))
    with pytest.raises(Exit, match=r"failed"):
        check.all_(c)


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


def test_all_missing_tool_stops_before_any_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("ruff"))
    c = _context({"tasks": "format-python,lint,types"})
    with pytest.raises(Exit, match=r"1 tool\(s\) missing for the selected steps"):
        check.all_(c)
    assert commands(c) == []


def test_all_missing_tools_are_all_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("ruff"))
    c = _context({"tasks": "format-python,format-docstrings,types,spelling"})
    with pytest.raises(Exit, match=r"3 tool\(s\) missing") as info:
        check.all_(c)
    assert str(info.value) == (
        "3 tool(s) missing for the selected steps:\n"
        "  'docformatter' was not found on the PATH or next to the "
        "Python interpreter. Install it with the 'dev' group: "
        "`uv sync --group dev`. (needed by: format-docstrings)\n"
        "  'ty' was not found on the PATH or next to the "
        "Python interpreter. Install it with the 'dev' group: "
        "`uv sync --group dev`. (needed by: types)\n"
        "  'codespell' was not found on the PATH or next to the "
        "Python interpreter. Add codespell to the dependencies of the "
        "project, e.g. `uv add --dev codespell`. (needed by: spelling)"
    )


def test_all_missing_tool_shared_by_steps_is_listed_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available())
    with pytest.raises(
        Exit, match=r"1 tool\(s\) missing .*\n  'ruff' .*\(needed by: format-python, lint\)"
    ):
        check.all_(_context({"tasks": "format-python,lint"}))


def test_all_does_not_look_up_the_tools_of_skipped_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("ruff"))
    c = _context({"tasks": "lint,types"})
    check.all_(c, skip="types")
    assert commands(c) == ["ruff check ."]


def test_all_missing_module_names_the_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available())
    with pytest.raises(
        Exit, match=r"The Python module 'pytest' is not installed .*\(needed by: unit\)"
    ):
        check.all_(_context({"tasks": "unit"}))


def test_all_keep_going_does_not_run_a_step_with_a_missing_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("ruff"))
    c = _context({"tasks": "lint,types"})
    with pytest.raises(Exit, match=r"1 of 2 check\(s\) failed: types"):
        check.all_(c, keep_going=True)
    assert commands(c) == ["ruff check ."]


##################################################
#     Tests for the missing tools of the steps   #
##################################################


def _missing_tools(step: str, cfg: TasklibConfig) -> list[tuple[str, str]]:
    return missing_tools(*check.STEPS[step].needs(cfg))


def _cfg(xdoctest: bool = True, timeout: bool = True) -> TasklibConfig:
    test = {"xdoctest": xdoctest, "timeout": timeout}
    return load_config(make_context({"package": {"name": "mypkg"}, "test": test}))


def test_missing_tools_unit_needs_pytest_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("pytest", "xdoctest"))
    assert [name for name, _ in _missing_tools("unit", _cfg())] == ["pytest_timeout"]


def test_missing_tools_unit_does_not_need_pytest_timeout_when_it_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("pytest", "xdoctest"))
    assert _missing_tools("unit", _cfg(timeout=False)) == []


def test_missing_tools_none_missing() -> None:
    assert _missing_tools("lint", _cfg()) == []


def test_missing_tools_step_without_tools() -> None:
    assert _missing_tools("imports", _cfg()) == []


def test_missing_tools_program(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available())
    assert _missing_tools("types", _cfg()) == [
        (
            "ty",
            (
                "'ty' was not found on the PATH or next to the "
                "Python interpreter. "
                "Install it with the 'dev' group: `uv sync --group dev`."
            ),
        )
    ]


def test_missing_tools_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("pytest_timeout", "xdoctest"))
    assert _missing_tools("unit", _cfg()) == [
        (
            "pytest",
            (
                "The Python module 'pytest' is not installed for /venv/bin/python. "
                "Install it with the 'dev' group: `uv sync --group dev`."
            ),
        )
    ]


def test_missing_tools_programs_come_before_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available())
    names = [name for name, _ in _missing_tools("audit", _cfg())]
    assert names == ["uv", "uvx"]


def test_missing_tools_unit_needs_xdoctest_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("pytest", "pytest_timeout"))
    assert [name for name, _ in _missing_tools("unit", _cfg(xdoctest=True))] == ["xdoctest"]


def test_missing_tools_unit_does_not_need_xdoctest_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("pytest", "pytest_timeout"))
    assert _missing_tools("unit", _cfg(xdoctest=False)) == []


def test_missing_tools_looks_modules_up_as_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    def find(name: str, *, module: bool = False) -> str:
        calls.append((name, module))
        return name

    monkeypatch.setattr(_steps, "find_tool", find)
    _missing_tools("doctest", _cfg())
    assert calls == [("pytest", True), ("xdoctest", True)]


###########################
#     Tests for _unit     #
###########################


def test_unit_without_cov() -> None:
    c = _context()
    check._unit(c)
    assert commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 10 tests/unit"]


def test_unit_with_cov() -> None:
    c = _context({"cov": True})
    check._unit(c)
    assert "--cov=mypkg" in commands(c)[0]


############################
#     Tests for _shell     #
############################


@pytest.fixture
def _scripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "run.sh").write_text("")
    monkeypatch.chdir(tmp_path)


@pytest.mark.usefixtures("_scripts")
def test_shell_runs_the_lint_then_the_format_check() -> None:
    c = _context()
    check._shell(c)
    assert commands(c) == ["shellcheck -- run.sh", "shfmt -d -- run.sh"]


###########################
#     Tests for STEPS     #
###########################


def test_shell_step_is_the_shell_wrapper() -> None:
    assert check.STEPS["shell"].task is check._shell


def test_shell_step_needs_shellcheck_and_shfmt() -> None:
    assert check.STEPS["shell"].programs == ("shellcheck", "shfmt")


def test_unit_step_is_the_unit_wrapper() -> None:
    assert check.STEPS["unit"].task is check._unit


def test_steps_are_the_valid_steps_of_the_config() -> None:
    assert tuple(check.STEPS) == CHECK_STEPS


############################################
#     Tests for the tools of the steps     #
############################################


def test_programs_are_checked_by_env_check_tools() -> None:
    programs = {name for step in check.STEPS.values() for name in step.needs(_cfg())[0]}
    assert programs <= {n for n, t in TOOLS.items() if t.kind == "program"}


def test_modules_are_checked_by_env_check_tools() -> None:
    cfg = _cfg()
    modules = {name for step in check.STEPS.values() for name in step.needs(cfg)[1]}
    assert modules <= {n for n, t in TOOLS.items() if t.kind == "module"}


def test_programs_of_the_steps_have_an_install_hint() -> None:
    programs = {name for step in check.STEPS.values() for name in step.needs(_cfg())[0]}
    assert programs <= set(TOOLS)


###################################
#     Tests for _unit_modules     #
###################################


def test_unit_modules_with_everything_on() -> None:
    assert check._unit_modules(_cfg()) == ("pytest", "pytest_timeout", "xdoctest")


def test_unit_modules_without_timeout() -> None:
    assert check._unit_modules(_cfg(timeout=False)) == ("pytest", "xdoctest")


def test_unit_modules_without_xdoctest() -> None:
    assert check._unit_modules(_cfg(xdoctest=False)) == ("pytest", "pytest_timeout")


def test_unit_modules_with_everything_off() -> None:
    assert check._unit_modules(_cfg(xdoctest=False, timeout=False)) == ("pytest",)


def test_unit_step_modules_are_the_unit_modules() -> None:
    assert check.STEPS["unit"].needs(_cfg(timeout=False))[1] == ("pytest", "xdoctest")


def test_missing_tools_unit_needs_xdoctest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("pytest", "pytest_timeout"))
    assert [name for name, _ in _missing_tools("unit", _cfg())] == ["xdoctest"]


def test_missing_tools_unit_does_not_need_xdoctest_when_it_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("pytest", "pytest_timeout"))
    assert _missing_tools("unit", _cfg(xdoctest=False)) == []


def test_types_step_needs_the_configured_checker() -> None:
    cfg = get_config(make_context({"package": {"name": "p"}, "types": {"checker": "mypy"}}))
    assert check.STEPS["types"].needs(cfg)[0] == ("mypy",)


def test_types_step_needs_ty_by_default() -> None:
    assert check.STEPS["types"].needs(_cfg())[0] == ("ty",)
