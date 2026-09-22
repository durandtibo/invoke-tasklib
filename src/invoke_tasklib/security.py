r"""Security scanning tasks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from invoke.tasks import task

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)


@task
def audit(c: Context) -> None:
    r"""Audit installed dependencies for known vulnerabilities with pip-
    audit."""
    logger.info("🔒 Auditing dependencies for known vulnerabilities...")
    c.run("uv run pip-audit", pty=True)
    logger.info("✅ Dependency audit passed")
