r"""Helpers shared by ``check.all`` and ``fix.all``."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from invoke.exceptions import Exit, UnexpectedExit

from invoke_tasklib.output import say
from invoke_tasklib.runner import find_tool, not_found_message

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping

    from invoke.context import Context


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
        the message of an ``Exit``, or the command and the exit code of
        a command that failed (its output was already shown).

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
