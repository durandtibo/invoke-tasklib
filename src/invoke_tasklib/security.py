r"""Security scanning tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.output import say

if TYPE_CHECKING:
    from invoke.context import Context


@task
def audit(c: Context) -> None:
    r"""Audit installed dependencies for known vulnerabilities with pip-
    audit."""
    say(c, "🔒 Auditing dependencies for known vulnerabilities...")
    c.run("uv run pip-audit", pty=True)
    say(c, "✅ Dependency audit passed")
