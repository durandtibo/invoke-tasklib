r"""Composite task that runs the read-only checks."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from invoke.exceptions import Exit, UnexpectedExit
from invoke.tasks import task

from invoke_tasklib import doc, formatting, imports, lint, security, testing, typecheck
from invoke_tasklib.config import CHECK_STEPS, load_config
from invoke_tasklib.output import say

if TYPE_CHECKING:
    from collections.abc import Callable

    from invoke.context import Context

STEPS: dict[str, Callable[[Context], None]] = {
    "format-python": formatting.check_python,
    "format-docstrings": formatting.check_docstrings,
    "lint": lint.check_python,
    "types": typecheck.check,
    "imports": imports.check_cycles,
    "unit": testing.unit,
    "doctest": testing.doctest,
    "shell": formatting.check_shell,
    "spelling": lint.check_spelling,
    "docs": doc.build,
    "audit": security.audit,
}
r"""The task of each step of ``check.all``, by step name."""


def _parse_steps(option: str, value: str | None) -> list[str]:
    r"""Parse the ``--only`` or ``--skip`` option.

    Args:
        option: The name of the option, used in the error message.
        value: A comma-separated list of step names, or ``None``.

    Returns:
        The step names, without duplicates, in the order given. It is
        empty if ``value`` is ``None``.

    Raises:
        Exit: If a name is not one of ``CHECK_STEPS``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.check import _parse_steps
    >>> _parse_steps("--only", "lint, unit")
    ['lint', 'unit']
    >>> _parse_steps("--skip", None)
    []

    ```
    """
    names = list(dict.fromkeys(n.strip() for n in (value or "").split(",") if n.strip()))
    unknown = [n for n in names if n not in CHECK_STEPS]
    if unknown:
        msg = f"Unknown step {unknown} in {option}. Valid steps: {', '.join(CHECK_STEPS)}"
        raise Exit(msg, code=2)
    return names


def _select_steps(configured: tuple[str, ...], only: list[str], skip: list[str]) -> list[str]:
    r"""Select the steps to run.

    Args:
        configured: The steps of ``tasklib.check.tasks``.
        only: The steps of ``--only``. If not empty, they replace
            ``configured``.
        skip: The steps of ``--skip``, removed from the selection.

    Returns:
        The selected steps, in order.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.check import _select_steps
    >>> _select_steps(("lint", "unit"), [], ["unit"])
    ['lint']
    >>> _select_steps(("lint", "unit"), ["docs"], [])
    ['docs']

    ```
    """
    return [step for step in (only or configured) if step not in skip]


def _run_step(c: Context, step: str) -> str | None:
    r"""Run a step and report whether it failed.

    Args:
        c: The invoke context.
        step: The name of the step.

    Returns:
        ``None`` if the step passed, else the reason of the failure:
        the message of an ``Exit``, or the command and the exit code of
        a command that failed (its output was already shown).

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import MockContext
    >>> from invoke_tasklib.check import _run_step
    >>> cfg = {"tasklib": {"package": {"name": "mypkg"}}}
    >>> c = MockContext(config=Config(overrides=cfg), run=True)
    >>> result = _run_step(c, "unit")  # doctest: +ELLIPSIS
    🧪 ...
    >>> result is None
    True

    ```
    """
    try:
        STEPS[step](c)
    except UnexpectedExit as exc:
        result = exc.result
        return f"The command {result.command!r} exited with code {result.exited}"
    except Exit as exc:
        return str(exc).strip() or type(exc).__name__
    return None


@task(
    name="all",
    default=True,
    help={
        "keep_going": "Run every step and report all the failures, instead of stopping.",
        "only": f"Comma-separated steps to run instead of tasklib.check.tasks ({', '.join(CHECK_STEPS)}).",
        "skip": "Comma-separated steps to leave out.",
    },
)
def all_(
    c: Context,
    *,
    keep_going: bool = False,
    only: str | None = None,
    skip: str | None = None,
) -> None:
    r"""Run the main checks of the project.

    The steps are the ones of ``tasklib.check.tasks`` (by default
    ``format-python``, ``format-docstrings``, ``lint``, ``types``,
    ``imports`` and ``unit``), run in that order. The other steps are
    ``doctest``, ``shell``, ``spelling``, ``docs`` and ``audit``. None
    of them modifies a file. By default the first failure stops the
    task; with ``keep_going`` every step is run and the failed ones are
    listed at the end.

    Args:
        c: The invoke context.
        keep_going: If True, run all the steps even if one fails.
        only: Comma-separated steps to run instead of the configured
            ones.
        skip: Comma-separated steps to leave out.

    Raises:
        Exit: If a name of ``only`` or ``skip`` is unknown, or if
            ``keep_going`` is set and a step failed.
        UnexpectedExit: If a step fails and ``keep_going`` is not set.
    """
    cfg = load_config(c)
    steps = _select_steps(
        cfg.check.tasks, _parse_steps("--only", only), _parse_steps("--skip", skip)
    )
    say(c, "🔎 Running all the checks...")
    failed: list[str] = []
    for step in steps:
        if not keep_going:
            STEPS[step](c)
        elif (reason := _run_step(c, step)) is not None:
            say(c, f"❌ Step failed: {step}")
            say(c, textwrap.indent(reason, "   "))
            failed.append(step)
    if failed:
        msg = f"{len(failed)} of {len(steps)} check(s) failed: {', '.join(failed)}"
        raise Exit(msg, code=1)
    say(c, "✅ All checks passed")
