r"""Lint tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.output import say

if TYPE_CHECKING:
    from invoke.context import Context


@task
def check_python(c: Context) -> None:
    r"""Check code linting with ruff."""
    say(c, "🔍 Checking code linting with ruff...")
    c.run("ruff check --output-format=github .", pty=True)
    say(c, "✅ Linting check passed")


@task
def fix_python(c: Context) -> None:
    r"""Fix auto-fixable linting issues in place with ruff.

    Note:
        This modifies files in place. Ensure your work is committed before
        running this task.
    """
    say(c, "🔧 Fixing linting issues with ruff...")
    c.run("ruff check --fix .", pty=True)
    say(c, "✅ Linting fix complete")
