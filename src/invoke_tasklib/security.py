r"""Security scanning tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.output import say
from invoke_tasklib.runner import run

if TYPE_CHECKING:
    from invoke.context import Context


@task
def audit(c: Context) -> None:
    r"""Audit the dependencies for known vulnerabilities.

    The audit is done with ``pip-audit``.
    """
    say(c, "🔒 Auditing dependencies for known vulnerabilities...")
    run(c, "uv run pip-audit")
    say(c, "✅ Dependency audit passed")
