r"""Lint tasks."""

from __future__ import annotations

import os
import shlex
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.output import say

if TYPE_CHECKING:
    from invoke.context import Context


@task(
    help={
        "output_format": (
            "Ruff output format. Defaults to 'github' when GITHUB_ACTIONS is 'true', "
            "ruff's own default otherwise."
        )
    }
)
def check_python(c: Context, output_format: str | None = None) -> None:
    r"""Check code linting with ruff.

    Args:
        c: The invoke context.
        output_format: The ``--output-format`` passed to ruff. If not set,
            ``github`` is used when running in GitHub Actions
            (``GITHUB_ACTIONS=true``), where it creates annotations, and
            ruff's default format is used otherwise.
    """
    if output_format is None and os.environ.get("GITHUB_ACTIONS") == "true":
        output_format = "github"
    say(c, "🔍 Checking code linting with ruff...")
    option = f" --output-format={shlex.quote(output_format)}" if output_format else ""
    c.run(f"ruff check{option} .", pty=True)
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
