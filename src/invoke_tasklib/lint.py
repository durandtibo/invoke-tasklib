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


@task
def fix(c: Context) -> None:
    r"""Fix auto-fixable linting issues in place with ruff.

    Note:
        This modifies files in place. Ensure your work is committed before
        running this task.
    """
    logger.info("🔧 Fixing linting issues with ruff...")
    c.run("ruff check --fix .", pty=True)
    logger.info("✅ Linting fix complete")
