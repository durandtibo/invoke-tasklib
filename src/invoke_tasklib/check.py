r"""Composite task that runs the read-only checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib import doc, formatting, imports, lint, security, testing, typecheck
from invoke_tasklib._steps import (
    Step,
    missing_tools,
    parse_steps,
    run_steps,
    select_steps,
    tasks_of,
)
from invoke_tasklib.config import CHECK_STEPS, load_config

if TYPE_CHECKING:
    from invoke.context import Context

    from invoke_tasklib.config import TasklibConfig

STEPS: dict[str, Step] = {
    "format-python": Step(formatting.check_python, programs=("ruff",)),
    "format-docstrings": Step(formatting.check_docstrings, programs=("docformatter",)),
    "lint": Step(lint.check_python, programs=("ruff",)),
    "types": Step(typecheck.check, programs=("ty",)),
    "imports": Step(imports.check_cycles),
    "unit": Step(testing.unit, modules=("pytest", "pytest_timeout")),
    "doctest": Step(testing.doctest, modules=("pytest", "xdoctest")),
    "shell": Step(formatting.check_shell, programs=("shellcheck",)),
    "spelling": Step(lint.check_spelling, programs=("codespell",)),
    "docs": Step(doc.build, programs=("mkdocs",)),
    "audit": Step(security.audit, programs=("uv", "uvx")),
}
r"""The steps of ``check.all`` (task, programs and Python modules), by
step name.

``unit`` also needs ``xdoctest`` if ``tasklib.test.xdoctest`` is true,
and does not need ``pytest_timeout`` if ``tasklib.test.timeout`` is
false. To add a step, add its name to ``CHECK_STEPS`` in
``config/_constants.py`` (a test checks that the names agree), and its
install hints to ``runner.py`` and its tools to ``env.py``."""


def _missing_tools(step: str, cfg: TasklibConfig) -> list[tuple[str, str]]:
    r"""List the tools of a step that are not available.

    Args:
        step: The name of the step.
        cfg: The resolved config.

    Returns:
        A ``(tool, reason)`` pair for each program of a step that
        is not on the ``PATH`` and each module of a step that is
        not installed, in that order. The reason says how to install it.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import MockContext
    >>> from invoke_tasklib.check import _missing_tools
    >>> from invoke_tasklib.config import load_config
    >>> cfg = {"tasklib": {"package": {"name": "p"}}}
    >>> c = MockContext(config=Config(overrides=cfg))
    >>> _missing_tools("imports", load_config(c))
    []

    ```
    """
    modules = STEPS[step].modules
    if step == "unit" and cfg.test.xdoctest:
        modules = (*modules, "xdoctest")
    return missing_tools(STEPS[step].programs, modules)


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

    Before any step is run, the tools that the selected steps need
    (the programs and modules of ``STEPS``) are looked up and all the
    missing ones are reported at once, with the code 127 and nothing
    run. With ``keep_going``, only the steps that miss a tool are not
    run: they are reported as failed, with the missing tools as the
    reason.

    Args:
        c: The invoke context.
        keep_going: If True, run all the steps even if one fails.
        only: Comma-separated steps to run instead of the configured
            ones.
        skip: Comma-separated steps to leave out.

    Raises:
        Exit: If a name of ``only`` or ``skip`` is unknown, if a tool
            of the selected steps is missing (code 127), or if
            ``keep_going`` is set and a step failed.
        UnexpectedExit: If a step fails and ``keep_going`` is not set.
    """
    cfg = load_config(c)
    steps = select_steps(
        cfg.check.tasks,
        parse_steps("--only", only, CHECK_STEPS),
        parse_steps("--skip", skip, CHECK_STEPS),
    )
    blocked = {step: missing for step in steps if (missing := _missing_tools(step, cfg))}
    run_steps(
        c,
        steps,
        tasks_of(STEPS),
        blocked,
        keep_going=keep_going,
        label="check(s)",
        messages=("🔎 Running all the checks...", "✅ All checks passed"),
    )
