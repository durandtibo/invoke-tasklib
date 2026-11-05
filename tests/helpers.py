from __future__ import annotations

import shlex
import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import runner, tools

if TYPE_CHECKING:
    import pytest

    from invoke_tasklib._steps import Step
    from invoke_tasklib.config import TasklibConfig


def make_context(tasklib_config: dict | None = None, run: object = True) -> MockContext:
    r"""Create a ``MockContext`` that records the commands it runs.

    Args:
        tasklib_config: The ``tasklib`` section of the config, or
            ``None`` for an empty config.
        run: The ``run`` argument of ``MockContext``. ``True`` makes
            every command succeed and records the calls.

    Returns:
        The mock context.
    """
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=run)


def run_kwargs(c: MockContext) -> list[dict]:
    r"""Return the keyword arguments passed to ``c.run``, in order.

    Args:
        c: A context created by ``make_context`` with ``run=True``.

    Returns:
        One dictionary of keyword arguments per call.
    """
    run = c.run
    assert isinstance(run, Mock)
    return [call.kwargs for call in run.call_args_list]


def commands(c: MockContext) -> list[str]:
    r"""Return the commands passed to ``c.run``, in order.

    Args:
        c: A context created by ``make_context`` with ``run=True``.

    Returns:
        The command strings.
    """
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


def step_needs_of_commands(
    step: Step, c: MockContext, monkeypatch: pytest.MonkeyPatch
) -> tuple[set[str], set[str]]:
    r"""Run the task of a step and return the tools that it checks.

    The commands that ``runner.run`` checks (not the ones run with
    ``check=False``) are read: the first word is a program, except for
    ``<interpreter> -m <module>``, whose module is returned instead,
    with the modules of the pytest plugins that the options need.

    Args:
        step: The step to run.
        c: A context created by ``make_context`` with ``run=True``.
        monkeypatch: The fixture used to record the checked commands.

    Returns:
        The ``(programs, modules)`` that the task runs with a check.
    """
    checked: list[list[str]] = []
    monkeypatch.setattr(
        runner, "check_program", lambda command: checked.append(shlex.split(command))
    )
    step.task(c)
    modules = {words[2] for words in checked if words[:2] == [sys.executable, "-m"]}
    modules |= {
        tools._PLUGIN_OPTIONS[option][0]
        for words in checked
        for option in (word.partition("=")[0] for word in words)
        if option in tools._PLUGIN_OPTIONS
    }
    programs = {words[0] for words in checked if words[0] != sys.executable}
    return programs, modules


def declared_needs(step: Step, cfg: TasklibConfig) -> tuple[set[str], set[str]]:
    r"""Return the tools that a step declares, as sets.

    Args:
        step: The step.
        cfg: The resolved config.

    Returns:
        The ``(programs, modules)`` of ``step.needs(cfg)``.
    """
    programs, modules = step.needs(cfg)
    return set(programs), set(modules)
