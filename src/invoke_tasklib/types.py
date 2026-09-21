r"""Type-checking tasks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import get_config

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)


@task
def check(c: Context) -> None:
    r"""Check type hints with pyright."""
    cfg = get_config(c)
    name = cfg["package"]["name"]
    logger.info("🔬 Checking type hints with pyright...")
    c.run(f"pyright --verifytypes {name} --ignoreexternal", pty=True)
    logger.info("✅ Type check passed")
