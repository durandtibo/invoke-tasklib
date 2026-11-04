from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.context import MockContext
from invoke.exceptions import Exit, Failure, UnexpectedExit
from invoke.runners import Result

from invoke_tasklib import _steps
from invoke_tasklib._steps import (
    Step,
    missing_tools,
    parse_steps,
    preflight_message,
    run_step,
    run_steps,
    select_steps,
    step_modules,
    tasks_of,
)
from invoke_tasklib.config import load_config
from tests.helpers import make_context

if TYPE_CHECKING:
    from collections.abc import Callable

    from invoke.context import Context

    from invoke_tasklib.config import TasklibConfig

_VALID = ("lint", "unit", "docs")
_MESSAGES = ("start", "done")


@pytest.fixture(autouse=True)
def _fixed_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")


def _available(*names: str) -> Callable[..., str | None]:
    r"""Return a ``find_tool`` that only finds the tools ``names``."""
    return lambda name, **_kwargs: f"/found/{name}" if name in names else None


def _tasks(calls: list[str], *failing: str) -> dict[str, Callable[[Context], None]]:
    r"""A task per step that records its name in ``calls``.

    The tasks of the steps ``failing`` then raise an ``Exit`` with their
    name.
    """

    def make(name: str) -> Callable[[Context], None]:
        def task(_c: Context) -> None:
            calls.append(name)
            if name in failing:
                msg = f"{name} failed"
                raise Exit(msg)

        return task

    return {name: make(name) for name in _VALID}


def _run(
    steps: list[str],
    *,
    failing: tuple[str, ...] = (),
    blocked: dict[str, list[tuple[str, str]]] | None = None,
    keep_going: bool = False,
) -> list[str]:
    r"""Run ``run_steps`` and return the steps that were called."""
    calls: list[str] = []
    run_steps(
        MockContext(run=True),
        steps,
        _tasks(calls, *failing),
        blocked or {},
        keep_going=keep_going,
        label="check(s)",
        messages=_MESSAGES,
    )
    return calls


###################################
#     Tests for missing_tools     #
###################################


def test_missing_tools_none_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available("ruff", "pytest"))
    assert missing_tools(["ruff"], ["pytest"]) == []


def test_missing_tools_nothing_to_look_up() -> None:
    assert missing_tools([], []) == []


def test_missing_tools_program(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available())
    assert missing_tools(["ruff"], []) == [
        (
            "ruff",
            (
                "'ruff' was not found on the PATH or next to the Python interpreter. "
                "Install it with the 'dev' group: `uv sync --group dev`."
            ),
        )
    ]


def test_missing_tools_module_names_the_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_steps, "find_tool", _available())
    assert missing_tools([], ["pytest"]) == [
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
    assert [name for name, _ in missing_tools(["ruff"], ["pytest"])] == ["ruff", "pytest"]


def test_missing_tools_looks_a_module_up_as_a_module(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    def find(name: str, *, module: bool = False) -> str:
        calls.append((name, module))
        return name

    monkeypatch.setattr(_steps, "find_tool", find)
    missing_tools(["ruff"], ["pytest"])
    assert calls == [("ruff", False), ("pytest", True)]


#################################
#     Tests for parse_steps     #
#################################


def test_parse_steps_none_is_empty() -> None:
    assert parse_steps("--only", None, _VALID) == []


def test_parse_steps_strips_and_removes_duplicates() -> None:
    assert parse_steps("--only", " lint , unit,lint", _VALID) == ["lint", "unit"]


def test_parse_steps_rejects_an_unknown_step() -> None:
    with pytest.raises(
        Exit, match=r"Unknown step \['x'\] in --skip. Valid steps: lint, unit, docs"
    ):
        parse_steps("--skip", "lint,x", _VALID)


def test_parse_steps_exits_with_code_2() -> None:
    with pytest.raises(Exit, match=r"Unknown step") as info:
        parse_steps("--skip", "x", _VALID)
    assert info.value.code == 2


##################################
#     Tests for select_steps     #
##################################


def test_select_steps_uses_the_configured_steps() -> None:
    assert select_steps(("lint", "unit"), [], []) == ["lint", "unit"]


def test_select_steps_only_wins_over_the_configured_steps() -> None:
    assert select_steps(("lint", "unit"), ["docs"], []) == ["docs"]


def test_select_steps_skip_removes_a_step() -> None:
    assert select_steps(("lint", "unit"), [], ["lint"]) == ["unit"]


def test_select_steps_does_not_mutate_its_inputs() -> None:
    only = ["lint", "unit"]
    select_steps((), only, ["lint"])
    assert only == ["lint", "unit"]


##############################
#     Tests for run_step     #
##############################


def test_run_step_passes() -> None:
    assert run_step(MockContext(), _tasks([]), "lint") is None


def test_run_step_returns_the_failure_message() -> None:
    assert run_step(MockContext(), _tasks([], "lint"), "lint") == "lint failed"


def test_run_step_returns_the_command_and_code_of_a_failed_command() -> None:
    def task(_c: Context) -> None:
        raise UnexpectedExit(Result(exited=3, command="ruff check"))

    assert run_step(MockContext(), {"lint": task}, "lint") == (
        "The command 'ruff check' exited with code 3"
    )


def test_run_step_names_the_exception_when_the_message_is_empty() -> None:
    task = Mock(side_effect=Exit())
    assert run_step(MockContext(), {"lint": task}, "lint") == "Exit"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (OSError("disk full"), "OSError: disk full"),
        (ValueError("bad value"), "ValueError: bad value"),
        (KeyError("key"), "KeyError: 'key'"),
        (AttributeError("no attr"), "AttributeError: no attr"),
        (ZeroDivisionError("division by zero"), "ZeroDivisionError: division by zero"),
        (ModuleNotFoundError("No module named 'x'"), "ModuleNotFoundError: No module named 'x'"),
        (TypeError("bad type"), "TypeError: bad type"),
        (RuntimeError("broken"), "RuntimeError: broken"),
    ],
)
def test_run_step_returns_the_type_and_message_of_an_error(error: Exception, reason: str) -> None:
    task = Mock(side_effect=error)
    assert run_step(MockContext(), {"lint": task}, "lint") == reason


def test_run_step_returns_the_type_of_an_invoke_failure() -> None:
    task = Mock(side_effect=Failure(Result(command="ruff")))
    assert (run_step(MockContext(), {"lint": task}, "lint") or "").startswith("Failure: ")


def test_run_step_returns_only_the_type_of_an_error_without_message() -> None:
    task = Mock(side_effect=RuntimeError())
    assert run_step(MockContext(), {"lint": task}, "lint") == "RuntimeError"


def test_run_step_does_not_catch_other_exceptions() -> None:
    task = Mock(side_effect=KeyboardInterrupt("interrupted"))
    with pytest.raises(KeyboardInterrupt, match=r"interrupted"):
        run_step(MockContext(), {"lint": task}, "lint")


#######################################
#     Tests for preflight_message     #
#######################################


def test_preflight_message_one_tool() -> None:
    assert preflight_message({"lint": [("ruff", "Install it.")]}) == (
        "1 tool(s) missing for the selected steps:\n  Install it. (needed by: lint)"
    )


def test_preflight_message_merges_a_tool_of_several_steps() -> None:
    blocked = {"lint": [("ruff", "Install it.")], "unit": [("ruff", "Install it.")]}
    assert preflight_message(blocked) == (
        "1 tool(s) missing for the selected steps:\n  Install it. (needed by: lint, unit)"
    )


def test_preflight_message_does_not_mutate_its_input() -> None:
    blocked = {"lint": [("ruff", "Install it.")]}
    preflight_message(blocked)
    assert blocked == {"lint": [("ruff", "Install it.")]}


###############################
#     Tests for run_steps     #
###############################


def test_run_steps_runs_the_steps_in_order() -> None:
    assert _run(["unit", "lint"]) == ["unit", "lint"]


def test_run_steps_stops_at_the_first_failure() -> None:
    calls: list[str] = []
    with pytest.raises(Exit, match=r"lint failed"):
        run_steps(
            MockContext(run=True),
            ["lint", "unit"],
            _tasks(calls, "lint"),
            {},
            keep_going=False,
            label="check(s)",
            messages=_MESSAGES,
        )
    assert calls == ["lint"]


def test_run_steps_keep_going_runs_every_step() -> None:
    calls: list[str] = []
    with pytest.raises(Exit, match=r"1 of 2 check\(s\) failed: lint"):
        run_steps(
            MockContext(run=True),
            ["lint", "unit"],
            _tasks(calls, "lint"),
            {},
            keep_going=True,
            label="check(s)",
            messages=_MESSAGES,
        )
    assert calls == ["lint", "unit"]


def test_run_steps_keep_going_continues_after_an_error_of_a_step() -> None:
    calls: list[str] = []

    def broken(_c: Context) -> None:
        msg = "disk full"
        raise OSError(msg)

    tasks = {"lint": broken, "unit": lambda _c: calls.append("unit")}
    with pytest.raises(Exit, match=r"1 of 2 check\(s\) failed: lint"):
        run_steps(
            MockContext(run=True),
            ["lint", "unit"],
            tasks,
            {},
            keep_going=True,
            label="check(s)",
            messages=("start", "done"),
        )
    assert calls == ["unit"]


def test_run_steps_keep_going_prints_the_error_of_a_step(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def broken(_c: Context) -> None:
        msg = "disk full"
        raise OSError(msg)

    with pytest.raises(Exit, match=r"failed: lint"):
        run_steps(
            MockContext(run=True),
            ["lint"],
            {"lint": broken},
            {},
            keep_going=True,
            label="check(s)",
            messages=("start", "done"),
        )
    assert "   OSError: disk full\n" in capsys.readouterr().err


def test_run_steps_keep_going_exits_with_code_1() -> None:
    with pytest.raises(Exit, match=r"failed") as info:
        run_steps(
            MockContext(run=True),
            ["lint"],
            _tasks([], "lint"),
            {},
            keep_going=True,
            label="x",
            messages=_MESSAGES,
        )
    assert info.value.code == 1


def test_run_steps_uses_the_label_in_the_failure_message() -> None:
    with pytest.raises(Exit, match=r"1 of 1 fix\(es\) failed: lint"):
        run_steps(
            MockContext(run=True),
            ["lint"],
            _tasks([], "lint"),
            {},
            keep_going=True,
            label="fix(es)",
            messages=_MESSAGES,
        )


def test_run_steps_says_start_then_done(capsys: pytest.CaptureFixture[str]) -> None:
    _run(["lint"])
    assert capsys.readouterr().out == "start\ndone\n"


def test_run_steps_blocked_stops_before_any_step() -> None:
    calls: list[str] = []
    with pytest.raises(Exit, match=r"1 tool\(s\) missing") as info:
        run_steps(
            MockContext(run=True),
            ["lint"],
            _tasks(calls),
            {"lint": [("ruff", "Install.")]},
            keep_going=False,
            label="x",
            messages=_MESSAGES,
        )
    assert (calls, info.value.code) == ([], 127)


def test_run_steps_blocked_with_keep_going_skips_only_that_step() -> None:
    calls: list[str] = []
    with pytest.raises(Exit, match=r"1 of 2 x failed: lint"):
        run_steps(
            MockContext(run=True),
            ["lint", "unit"],
            _tasks(calls),
            {"lint": [("ruff", "Install.")]},
            keep_going=True,
            label="x",
            messages=_MESSAGES,
        )
    assert calls == ["unit"]


def test_run_steps_keep_going_prints_the_reason(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(Exit, match=r"failed"):
        run_steps(
            MockContext(run=True),
            ["lint"],
            _tasks([], "lint"),
            {},
            keep_going=True,
            label="x",
            messages=_MESSAGES,
        )
    assert capsys.readouterr().err == "❌ Step failed: lint\n   lint failed\n"


##########################
#     Tests for Step     #
##########################


def _noop(_c: object) -> None:
    return None


def test_step_has_no_tools_by_default() -> None:
    assert Step(_noop) == (_noop, (), ())


def test_step_keeps_programs_and_modules() -> None:
    step = Step(_noop, programs=("ruff",), modules=("pytest",))
    assert (step.programs, step.modules) == (("ruff",), ("pytest",))


##############################
#     Tests for tasks_of     #
##############################


def test_tasks_of_returns_the_task_of_each_step() -> None:
    other = Mock()
    assert tasks_of({"a": Step(_noop), "b": Step(other)}) == {"a": _noop, "b": other}


def test_tasks_of_no_step_is_empty() -> None:
    assert tasks_of({}) == {}


###################################
#     Tests for step_modules      #
###################################


def _config(*, xdoctest: bool = True) -> TasklibConfig:
    tasklib = {"package": {"name": "mypkg"}, "test": {"xdoctest": xdoctest}}
    return load_config(make_context(tasklib))


def test_step_modules_returns_a_tuple_as_it_is() -> None:
    step = Step(lambda _c: None, modules=("pytest", "xdoctest"))
    assert step_modules(step, _config()) == ("pytest", "xdoctest")


def test_step_modules_of_a_step_without_modules_is_empty() -> None:
    assert step_modules(Step(lambda _c: None), _config()) == ()


def test_step_modules_calls_a_function_with_the_config() -> None:
    step = Step(lambda _c: None, modules=lambda cfg: ("xdoctest",) if cfg.test.xdoctest else ())
    assert step_modules(step, _config(xdoctest=False)) == ()


def test_step_modules_calls_a_function_each_time() -> None:
    calls = Mock(return_value=("a",))
    step = Step(lambda _c: None, modules=calls)
    step_modules(step, _config())
    step_modules(step, _config())
    assert calls.call_count == 2
