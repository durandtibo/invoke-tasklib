r"""Composite task that runs the read-only checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib import formatting, imports, lint, testing, typecheck
from invoke_tasklib.output import say

if TYPE_CHECKING:
    from invoke.context import Context


@task(name="all", default=True)
def all_(c: Context) -> None:
    r"""Run the main checks of the project.

    The checks are run in this order, and the first failure stops the
    task: ``format.check-python``, ``format.check-docstrings``,
    ``lint.check-python``, ``types.check``, ``imports.check-cycles`` and
    ``test.unit``. None of them modifies a file.

    Args:
        c: The invoke context.

    Raises:
        UnexpectedExit: If a check fails.
    """
    say(c, "🔎 Running all the checks...")
    formatting.check_python(c)
    formatting.check_docstrings(c)
    lint.check_python(c)
    typecheck.check(c)
    imports.check_cycles(c)
    testing.unit(c)
    say(c, "✅ All checks passed")
