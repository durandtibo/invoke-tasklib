r"""Documentation publishing tasks (versioned docs via mike)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import get_config

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)


@task
def publish_dev(c: Context) -> None:
    r"""Publish development (e.g. unstable) docs."""
    cfg = get_config(c)
    docs_config = cfg["paths"]["docs_config"]
    logger.info("📚 Publishing development documentation...")
    logger.info("🗑️  Deleting previous 'main' version if it exists...")
    c.run(f"mike delete --config-file {docs_config} main", pty=True, warn=True)
    logger.info("🚀 Deploying 'main' and 'dev' aliases...")
    c.run(f"mike deploy --config-file {docs_config} --push --update-aliases main dev", pty=True)
    logger.info("✅ Development documentation published")


@task
def publish_latest(c: Context) -> None:
    r"""Publish latest (e.g. stable) docs.

    Requires the ``feu`` and ``packaging`` packages to determine the
    latest version tag.
    """
    from feu.local_git import get_last_version_tag_name  # noqa: PLC0415 (optional dependency)
    from packaging.version import Version  # noqa: PLC0415 (optional dependency)

    cfg = get_config(c)
    docs_config = cfg["paths"]["docs_config"]
    logger.info("📚 Publishing latest documentation...")

    try:
        tag_name = get_last_version_tag_name()
    except RuntimeError:
        tag_name = None

    if tag_name is None:
        tag = "0.0"
        logger.warning("⚠️  No version tag found, using default: 0.0")
    else:
        version = Version(tag_name)
        tag = f"{version.major}.{version.minor}"
        logger.info("📌 Using version tag: %s", tag)

    logger.info("🗑️  Deleting previous '%s' version if it exists...", tag)
    c.run(f"mike delete --config-file {docs_config} {tag}", pty=True, warn=True)
    logger.info("🚀 Deploying '%s' and 'latest' aliases...", tag)
    c.run(f"mike deploy --config-file {docs_config} --push --update-aliases {tag} latest", pty=True)
    logger.info("🎯 Setting 'latest' as default...")
    c.run(f"mike set-default --config-file {docs_config} --push --allow-empty latest", pty=True)
    logger.info("✅ Latest documentation published")
