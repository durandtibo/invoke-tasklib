r"""Documentation publishing tasks (versioned docs via mike)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import get_config
from invoke_tasklib.output import say

if TYPE_CHECKING:
    from invoke.context import Context


@task
def publish_dev(c: Context) -> None:
    r"""Publish development (e.g. unstable) docs."""
    cfg = get_config(c)
    docs_config = cfg["paths"]["docs_config"]
    say(c, "📚 Publishing development documentation...")
    say(c, "🗑️  Deleting previous 'main' version if it exists...")
    c.run(f"mike delete --config-file {docs_config} main", pty=True, warn=True)
    say(c, "🚀 Deploying 'main' and 'dev' aliases...")
    c.run(f"mike deploy --config-file {docs_config} --push --update-aliases main dev", pty=True)
    say(c, "✅ Development documentation published")


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
    say(c, "📚 Publishing latest documentation...")

    try:
        tag_name = get_last_version_tag_name()
    except RuntimeError:
        tag_name = None

    if tag_name is None:
        tag = "0.0"
        say(c, "⚠️  No version tag found, using default: 0.0")
    else:
        version = Version(tag_name)
        tag = f"{version.major}.{version.minor}"
        say(c, f"📌 Using version tag: {tag}")

    say(c, f"🗑️  Deleting previous '{tag}' version if it exists...")
    c.run(f"mike delete --config-file {docs_config} {tag}", pty=True, warn=True)
    say(c, f"🚀 Deploying '{tag}' and 'latest' aliases...")
    c.run(f"mike deploy --config-file {docs_config} --push --update-aliases {tag} latest", pty=True)
    say(c, "🎯 Setting 'latest' as default...")
    c.run(f"mike set-default --config-file {docs_config} --push --allow-empty latest", pty=True)
    say(c, "✅ Latest documentation published")
