r"""Composite task that runs the read-only checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib import doc, formatting, imports, lint, security, testing, typecheck
from invoke_tasklib._steps import Step, run_composite
from invoke_tasklib.config import load_config
from invoke_tasklib.config._constants import CHECK_STEPS

if TYPE_CHECKING:
    from invoke.context import Context

    from invoke_tasklib.config import TasklibConfig


NAMESPACE = "check"
r"""The name of the namespace of the tasks of this module."""


def _unit(c: Context) -> None:
    r"""Run the unit tests, with coverage if ``tasklib.check.cov``.

    With coverage, ``tasklib.test.cov_fail_under`` is enforced, as it is
    by ``test.unit --cov``.

    Args:
        c: The invoke context.
    """
    testing.unit(c, cov=load_config(c).check.cov)


def _shell(c: Context) -> None:
    r"""Check the shell scripts: the lint, then the format.

    It runs ``format.check-shell`` (shellcheck) and
    ``format.check-shell-format`` (``shfmt -d``), so the ``shell`` step
    of ``check.all`` accepts what the ``shell`` step of ``fix.all``
    would leave unchanged.

    Args:
        c: The invoke context.
    """
    formatting.check_shell(c)
    formatting.check_shell_format(c)


def _unit_modules(cfg: TasklibConfig) -> tuple[str, ...]:
    r"""List the Python modules that the ``unit`` step needs.

    Args:
        cfg: The resolved config.

    Returns:
        ``pytest``, plus ``pytest_timeout`` if ``tasklib.test.timeout``
        is true and ``xdoctest`` if ``tasklib.test.xdoctest`` is true.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import MockContext
    >>> from invoke_tasklib.check import _unit_modules
    >>> from invoke_tasklib.config import load_config
    >>> cfg = {"tasklib": {"package": {"name": "p"}}}
    >>> c = MockContext(config=Config(overrides=cfg))
    >>> _unit_modules(load_config(c))
    ('pytest', 'pytest_timeout', 'xdoctest')

    ```
    """
    return (
        "pytest",
        *(("pytest_timeout",) if cfg.test.timeout else ()),
        *(("xdoctest",) if cfg.test.xdoctest else ()),
    )


_STEPS: dict[str, Step] = {
    "format-python": Step(formatting.check_python, programs=("ruff",)),
    "format-docstrings": Step(formatting.check_docstrings, programs=("docformatter",)),
    "lint": Step(lint.check_python, programs=("ruff",)),
    "types": Step(typecheck.check, programs=lambda cfg: (cfg.types.checker,)),
    "imports": Step(imports.check_cycles),
    "unit": Step(_unit, modules=_unit_modules),
    "doctest": Step(testing.doctest, modules=("pytest", "xdoctest")),
    "shell": Step(_shell, programs=("shellcheck", "shfmt")),
    "spelling": Step(lint.check_spelling, programs=("codespell",)),
    "docs": Step(doc.build, programs=("mkdocs",)),
    "audit": Step(security.audit, programs=("uv", "uvx")),
}
r"""The steps of ``check.all`` (task, programs and Python modules), by
step name.

The modules of ``unit`` depend on the config, see ``_unit_modules``. To
add a step, add its name to ``CHECK_STEPS`` in ``config/_constants.py``
(a test checks that the names agree), and its programs and install hints
to ``TOOLS`` in ``tools.py``.
"""


@task(
    name="all",
    default=True,
    help={
        "keep_going": "Run every step and report all the failures, instead of stopping.",
        "only": (
            f"Comma-separated steps to run instead of tasklib.check.tasks "
            f"({', '.join(CHECK_STEPS)})."
        ),
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
    (the programs and modules of ``_STEPS``) are looked up and all the
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
    run_composite(
        c,
        cfg,
        _STEPS,
        CHECK_STEPS,
        cfg.check.tasks,
        only=only,
        skip=skip,
        keep_going=keep_going,
        label="check(s)",
        messages=("🔎 Running all the checks...", "✅ All checks passed"),
    )
