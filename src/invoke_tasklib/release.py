r"""Build and publish tasks (PyPI package)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import get_config

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)


@task
def build(c: Context, check: bool = False) -> None:
    r"""Build the package and verify it can be installed.

    Args:
        c: The invoke context.
        check: If True, also check the package's PyPI metadata with
            twine. Default is False.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    logger.info("📦 Building package...")
    c.run("uv build", pty=True)
    logger.info("🔍 Verifying package installation...")
    c.run(
        f'uv run --with {name} --refresh-package {name} --no-project -- python -c "import {name}"',
        pty=True,
    )
    if check:
        logger.info("🔍 Checking package metadata with twine...")
        c.run("uvx twine check dist/*", pty=True)


@task
def pypi(c: Context) -> None:
    r"""Build and publish the package to PyPI."""
    build(c)
    logger.info("🚀 Publishing to PyPI...")
    c.run("uv publish --token ${PYPI_TOKEN}", pty=True)
    logger.info("✅ Package published successfully")
