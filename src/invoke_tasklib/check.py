r"""Composite task that runs the read-only checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib import doc, formatting, imports, lint, security, testing, typecheck
from invoke_tasklib._steps import missing_tools, parse_steps, run_steps, select_steps
from invoke_tasklib.config import CHECK_STEPS, load_config

if TYPE_CHECKING:
    from collections.abc import Callable

    from invoke.context import Context

    from invoke_tasklib.config import TasklibConfig


def _unit(c: Context) -> None:
    r"""Run the unit tests, with coverage if ``tasklib.check.cov``.

    With coverage, ``tasklib.test.cov_fail_under`` is enforced, as it is
    by ``test.unit --cov``.

    Args:
        c: The invoke context.
    """
    testing.unit(c, cov=load_config(c).check.cov)


STEPS: dict[str, Callable[[Context], None]] = {
    "format-python": formatting.check_python,
    "format-docstrings": formatting.check_docstrings,
    "lint": lint.check_python,
    "types": typecheck.check,
    "imports": imports.check_cycles,
    "unit": _unit,
    "doctest": testing.doctest,
    "shell": formatting.check_shell,
    "spelling": lint.check_spelling,
    "docs": doc.build,
    "audit": security.audit,
}
r"""The task of each step of ``check.all``, by step name."""

PROGRAMS: dict[str, tuple[str, ...]] = {
    "format-python": ("ruff",),
    "format-docstrings": ("docformatter",),
    "lint": ("ruff",),
    "types": ("ty",),
    "imports": (),
    "unit": (),
    "doctest": (),
    "shell": ("shellcheck",),
    "spelling": ("codespell",),
    "docs": ("mkdocs",),
    "audit": ("uv", "uvx"),
}
r"""The programs that each step of ``check.all`` runs, by step name."""

# The Python modules that each step of ``check.all`` runs, by step name.
# ``unit`` also needs ``xdoctest`` if ``tasklib.test.xdoctest`` is true,
# and does not need ``pytest_timeout`` if ``tasklib.test.timeout`` is
# false.
MODULES: dict[str, tuple[str, ...]] = {
    "format-python": (),
    "format-docstrings": (),
    "lint": (),
    "types": (),
    "imports": (),
    "unit": ("pytest", "pytest_timeout"),
    "doctest": ("pytest", "xdoctest"),
    "shell": (),
    "spelling": (),
    "docs": (),
    "audit": (),
}


def _missing_tools(step: str, cfg: TasklibConfig) -> list[tuple[str, str]]:
    r"""List the tools of a step that are not available.

    Args:
        step: The name of the step.
        cfg: The resolved config.

    Returns:
        A ``(tool, reason)`` pair for each program of ``PROGRAMS`` that
        is not on the ``PATH`` and each module of ``MODULES`` that is
        not installed, in that order. The reason says how to install it.
        ``xdoctest`` is only needed with ``tasklib.test.xdoctest`` and
        ``pytest_timeout`` only with ``tasklib.test.timeout``.

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
    modules = MODULES[step]
    if step == "unit" and cfg.test.xdoctest:
        modules = (*modules, "xdoctest")
    if step == "unit" and not cfg.test.timeout:
        modules = tuple(module for module in modules if module != "pytest_timeout")
    return missing_tools(PROGRAMS[step], modules)


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
    of them modifies a file (except the coverage reports of ``unit``
    with ``tasklib.check.cov``, which also enforces
    ``tasklib.test.cov_fail_under``). By default the first failure
    stops the task; with ``keep_going`` every step is run and the
    failed ones are listed at the end.

    Before any step is run, the tools that the selected steps need
    (``PROGRAMS`` and ``MODULES``) are looked up and all the missing
    ones are reported at once, with the code 127 and nothing run. With
    ``keep_going``, only the steps that miss a tool are not run: they
    are reported as failed, with the missing tools as the reason.

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
        STEPS,
        blocked,
        keep_going=keep_going,
        label="check(s)",
        messages=("🔎 Running all the checks...", "✅ All checks passed"),
    )
