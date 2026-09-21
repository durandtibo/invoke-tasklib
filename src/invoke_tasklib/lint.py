r"""Lint tasks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from invoke.tasks import task

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)


@task
def check_lint(c: Context) -> None:
    r"""Check code linting with ruff."""
    logger.info("🔍 Checking code linting with ruff...")
    c.run("ruff check --output-format=github .", pty=True)
    logger.info("✅ Linting check passed")
