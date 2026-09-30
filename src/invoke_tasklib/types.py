r"""Type-checking tasks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from invoke.tasks import task

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)


@task
def check(c: Context) -> None:
    r"""Check type hints with ty."""
    logger.info("🔬 Checking type hints with ty...")
    c.run("ty check", pty=True)
    logger.info("✅ Type check passed")
