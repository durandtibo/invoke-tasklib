r"""Helpers shared by ``check.all`` and ``fix.all``."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING, NamedTuple

from invoke.exceptions import Exit, Failure, UnexpectedExit

from invoke_tasklib.output import say
from invoke_tasklib.tools import find_tool, not_found_message

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping

    from invoke.context import Context

    from invoke_tasklib.config import TasklibConfig


STEP_ERRORS: tuple[type[Exception], ...] = (
    ArithmeticError,
    AttributeError,
    Failure,
    ImportError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
r"""The errors of a step, other than ``Exit`` and ``UnexpectedExit``,
that ``run_step`` reports as the reason of a failure.

A step is a task, so it can also fail with an error of the code (a bug)
or of the system (a missing file) or with another failure of Invoke (a
timeout). ``KeyboardInterrupt`` and ``SystemExit`` are not listed: they
stop the run.
"""


class Step(NamedTuple):
    r"""A step of ``check.all`` or ``fix.all``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._steps import Step
    >>> Step(lambda c: None, programs=("ruff",)).programs
    ('ruff',)

    ```
    """

    task: Callable[[Context], None]
    r"""The task that runs the step."""

    programs: tuple[str, ...] | Callable[[TasklibConfig], tuple[str, ...]] = ()
    r"""The programs that the step runs, looked up on the ``PATH``, or a
    function of the config that returns them (the ``types`` step runs
    the configured checker), see ``needs``."""

    modules: tuple[str, ...] | Callable[[TasklibConfig], tuple[str, ...]] = ()
    r"""The Python modules that the step runs, or a function of the
    config that returns them (a step whose modules depend on the
    options), see ``needs``."""

    def needs(self, cfg: TasklibConfig) -> tuple[tuple[str, ...], tuple[str, ...]]:
        r"""Return the programs and the modules that the step needs.

        Args:
            cfg: The resolved config, given to ``programs`` and
                ``modules`` if they are functions.

        Returns:
            The ``(programs, modules)`` of the step, as tuples.

        Example usage:

        ```pycon
        >>> from invoke_tasklib._steps import Step
        >>> step = Step(print, ("ruff",), lambda cfg: ("pytest",))
        >>> step.needs(None)
        (('ruff',), ('pytest',))

        ```
        """
        programs, modules = self.programs, self.modules
        return (
            programs if isinstance(programs, tuple) else programs(cfg),
            modules if isinstance(modules, tuple) else modules(cfg),
        )


def missing_tools(programs: Collection[str], modules: Collection[str]) -> list[tuple[str, str]]:
    r"""List the tools that are not available.

    Args:
        programs: The programs to look up on the ``PATH``.
        modules: The Python modules to look up for the running
            interpreter.

    Returns:
        A ``(tool, reason)`` pair for each program that is not on the
        ``PATH`` and each module that is not installed, in that order.
        The reason says how to install it.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._steps import missing_tools
    >>> missing_tools([], [])
    []

    ```
    """
    missing = [(name, not_found_message(name)) for name in programs if find_tool(name) is None]
    missing.extend(
        (name, not_found_message(name, module=True))
        for name in modules
        if find_tool(name, module=True) is None
    )
    return missing


def preflight_message(blocked: Mapping[str, list[tuple[str, str]]]) -> str:
    r"""Build the message that lists the missing tools of the steps.

    Args:
        blocked: The missing tools (see ``missing_tools``) of each step
            that cannot run, by step name.

    Returns:
        A message with one line per missing tool: the reason, then the
        steps that need the tool.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._steps import preflight_message
    >>> print(preflight_message({"lint": [("ruff", "Install ruff.")]}))
    1 tool(s) missing for the selected steps:
      Install ruff. (needed by: lint)

    ```
    """
    steps_of: dict[str, list[str]] = {}
    reasons: dict[str, str] = {}
    for step, missing in blocked.items():
        for name, reason in missing:
            steps_of.setdefault(name, []).append(step)
            reasons.setdefault(name, reason)
    lines = [f"{len(steps_of)} tool(s) missing for the selected steps:"]
    lines.extend(f"  {reasons[name]} (needed by: {', '.join(steps_of[name])})" for name in steps_of)
    return "\n".join(lines)


def parse_steps(option: str, value: str | None, valid: tuple[str, ...]) -> list[str]:
    r"""Parse the ``--only`` or ``--skip`` option.

    Args:
        option: The name of the option, used in the error message.
        value: A comma-separated list of step names, or ``None``.
        valid: The valid step names.

    Returns:
        The step names, without duplicates, in the order given. It is
        empty if ``value`` is ``None``.

    Raises:
        Exit: If a name is not one of ``valid``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._steps import parse_steps
    >>> valid = ("lint", "unit")
    >>> parse_steps("--only", "lint, unit", valid)
    ['lint', 'unit']
    >>> parse_steps("--skip", None, valid)
    []

    ```
    """
    names = list(dict.fromkeys(n.strip() for n in (value or "").split(",") if n.strip()))
    unknown = [n for n in names if n not in valid]
    if unknown:
        msg = f"Unknown step {unknown} in {option}. Valid steps: {', '.join(valid)}"
        raise Exit(msg, code=2)
    return names


def select_steps(configured: tuple[str, ...], only: list[str], skip: list[str]) -> list[str]:
    r"""Select the steps to run.

    Args:
        configured: The steps of the config (``tasklib.check.tasks`` or
            ``tasklib.fix.tasks``).
        only: The steps of ``--only``. If not empty, they replace
            ``configured``.
        skip: The steps of ``--skip``, removed from the selection.

    Returns:
        The selected steps, in order.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._steps import select_steps
    >>> select_steps(("lint", "unit"), [], ["unit"])
    ['lint']
    >>> select_steps(("lint", "unit"), ["docs"], [])
    ['docs']

    ```
    """
    return [step for step in (only or configured) if step not in skip]


def run_step(c: Context, tasks: Mapping[str, Callable[[Context], None]], step: str) -> str | None:
    r"""Run a step and report whether it failed.

    Args:
        c: The invoke context.
        tasks: The task of each step, by step name.
        step: The name of the step.

    Returns:
        ``None`` if the step passed, else the reason of the failure:
        the message of an ``Exit``, the command and the exit code of
        a command that failed (its output was already shown), or the
        type and the message of an error of ``STEP_ERRORS`` (a bug in
        a task, an ``OSError``, a timeout), so one broken step does
        not hide the summary of the others. ``KeyboardInterrupt`` is
        not caught.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._steps import run_step
    >>> run_step(None, {"ok": lambda c: None}, "ok") is None
    True

    ```
    """
    try:
        tasks[step](c)
    except UnexpectedExit as exc:
        result = exc.result
        return f"The command {result.command!r} exited with code {result.exited}"
    except Exit as exc:
        return str(exc).strip() or type(exc).__name__
    except STEP_ERRORS as exc:
        return f"{type(exc).__name__}: {exc}".removesuffix(": ")
    return None


def run_steps(
    c: Context,
    steps: list[str],
    tasks: Mapping[str, Callable[[Context], None]],
    blocked: Mapping[str, list[tuple[str, str]]],
    *,
    keep_going: bool,
    label: str,
    messages: tuple[str, str],
) -> None:
    r"""Run the steps of a composite task.

    Args:
        c: The invoke context.
        steps: The names of the steps to run, in order.
        tasks: The task of each step, by step name.
        blocked: The missing tools (see ``missing_tools``) of the steps
            that cannot run, by step name. Without ``keep_going`` any
            entry stops everything before the first step. With it, only
            these steps are not run and they count as failed.
        keep_going: If True, run all the steps even if one fails.
        label: What the steps are called in the final message, e.g.
            ``"check(s)"``.
        messages: The message written before the first step and the
            message written when all the steps passed.

    Raises:
        Exit: If a tool is missing (code 127), or if ``keep_going`` is
            set and a step failed (code 1).
        UnexpectedExit: If a step fails and ``keep_going`` is not set.
    """
    if blocked and not keep_going:
        raise Exit(preflight_message(blocked), code=127)
    start, done = messages
    say(c, start)
    failed: list[str] = []
    for step in steps:
        if step in blocked:
            say(c, f"❌ Step failed: {step}", err=True)
            say(
                c,
                textwrap.indent("\n".join(reason for _, reason in blocked[step]), "   "),
                err=True,
            )
            failed.append(step)
        elif not keep_going:
            tasks[step](c)
        elif (reason := run_step(c, tasks, step)) is not None:
            say(c, f"❌ Step failed: {step}", err=True)
            say(c, textwrap.indent(reason, "   "), err=True)
            failed.append(step)
    if failed:
        msg = f"{len(failed)} of {len(steps)} {label} failed: {', '.join(failed)}"
        raise Exit(msg, code=1)
    say(c, done)


def run_composite(
    c: Context,
    cfg: TasklibConfig,
    steps: Mapping[str, Step],
    valid: tuple[str, ...],
    configured: tuple[str, ...],
    *,
    only: str | None,
    skip: str | None,
    keep_going: bool,
    label: str,
    messages: tuple[str, str],
) -> None:
    r"""Run a composite task: select the steps, look up the tools, run.

    The steps are the ones of ``configured``, or of ``only`` if it is
    set, without the ones of ``skip``. Before any step is run, the
    tools that the selected steps need are looked up (see
    ``Step.needs``) and the missing ones are reported, see
    ``run_steps``.

    Args:
        c: The invoke context.
        cfg: The resolved config.
        steps: The steps, by name.
        valid: The valid step names, for ``only`` and ``skip``.
        configured: The steps of the config.
        only: Comma-separated steps to run instead of ``configured``.
        skip: Comma-separated steps to leave out.
        keep_going: If True, run all the steps even if one fails.
        label: What the steps are called in the final message, e.g.
            ``"check(s)"``.
        messages: The message written before the first step and the
            message written when all the steps passed.

    Raises:
        Exit: If a name of ``only`` or ``skip`` is unknown (code 2), if
            a tool of the selected steps is missing (code 127), or if
            ``keep_going`` is set and a step failed (code 1).
        UnexpectedExit: If a step fails and ``keep_going`` is not set.
    """
    selected = select_steps(
        configured,
        parse_steps("--only", only, valid),
        parse_steps("--skip", skip, valid),
    )
    blocked = {
        name: missing for name in selected if (missing := missing_tools(*steps[name].needs(cfg)))
    }
    run_steps(
        c,
        selected,
        {name: step.task for name, step in steps.items()},
        blocked,
        keep_going=keep_going,
        label=label,
        messages=messages,
    )
