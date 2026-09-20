r"""Build and publish tasks (PyPI package, versioned docs)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import get_config

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)


@task
def build_package(c: Context) -> None:
    r"""Build the package and verify it can be installed."""
    cfg = get_config(c)
    name = cfg["package"]["name"]
    logger.info("📦 Building package...")
    c.run("uv build", pty=True)
    logger.info("🔍 Verifying package installation...")
    c.run(
        f'uv run --with {name} --refresh-package {name} --no-project -- python -c "import {name}"',
        pty=True,
    )


@task
def publish_pypi(c: Context) -> None:
    r"""Build and publish the package to PyPI."""
    build_package(c)
    logger.info("🚀 Publishing to PyPI...")
    c.run("uv publish --token ${PYPI_TOKEN}", pty=True)
    logger.info("✅ Package published successfully")


@task
def publish_doc_dev(c: Context) -> None:
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
def publish_doc_latest(c: Context) -> None:
    r"""Publish latest (e.g. stable) docs.

    Requires the ``feu`` and ``packaging`` packages to determine the latest
    version tag.
    """
    from feu.local_git import get_last_version_tag_name  # noqa: PLC0415
    from packaging.version import Version  # noqa: PLC0415

    cfg = get_config(c)
    docs_config = cfg["paths"]["docs_config"]
    logger.info("📚 Publishing latest documentation...")

    try:
        version = Version(get_last_version_tag_name())
        tag = f"{version.major}.{version.minor}"
        logger.info(f"📌 Using version tag: {tag}")
    except RuntimeError:
        tag = "0.0"
        logger.warning("⚠️  No version tag found, using default: 0.0")

    logger.info(f"🗑️  Deleting previous '{tag}' version if it exists...")
    c.run(f"mike delete --config-file {docs_config} {tag}", pty=True, warn=True)
    logger.info(f"🚀 Deploying '{tag}' and 'latest' aliases...")
    c.run(f"mike deploy --config-file {docs_config} --push --update-aliases {tag} latest", pty=True)
    logger.info("🎯 Setting 'latest' as default...")
    c.run(f"mike set-default --config-file {docs_config} --push --allow-empty latest", pty=True)
    logger.info("✅ Latest documentation published")
