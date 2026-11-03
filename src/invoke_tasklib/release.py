r"""Build and publish tasks (PyPI package)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import get_config
from invoke_tasklib.output import say

if TYPE_CHECKING:
    from invoke.context import Context


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
    say(c, "📦 Building package...")
    c.run("uv build", pty=True)
    say(c, "🔍 Verifying package installation...")
    c.run(
        f'uv run --with {name} --refresh-package {name} --no-project -- python -c "import {name}"',
        pty=True,
    )
    if check:
        say(c, "🔍 Checking package metadata with twine...")
        c.run("uvx twine check dist/*", pty=True)


@task
def pypi(c: Context) -> None:
    r"""Build and publish the package to PyPI."""
    build(c)
    say(c, "🚀 Publishing to PyPI...")
    c.run("uv publish --token ${PYPI_TOKEN}", pty=True)
    say(c, "✅ Package published successfully")
