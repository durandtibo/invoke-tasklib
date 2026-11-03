r"""Build and publish tasks (PyPI package)."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.exceptions import Exit
from invoke.tasks import task

from invoke_tasklib.config import get_config
from invoke_tasklib.output import say

if TYPE_CHECKING:
    from invoke.context import Context


def _latest_artifact(directory: Path, pattern: str) -> Path:
    r"""Return the most recently modified file matching a pattern.

    Args:
        directory: The directory to search.
        pattern: The glob pattern of the file name, e.g. ``"*.whl"``.

    Returns:
        The path of the most recently modified matching file.

    Raises:
        Exit: If no file matches the pattern.

    Example usage:

    ```pycon
    >>> import tempfile
    >>> from pathlib import Path
    >>> from invoke_tasklib.release import _latest_artifact
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     _ = (Path(tmp) / "pkg-1.0-py3-none-any.whl").write_text("")
    ...     _latest_artifact(Path(tmp), "*.whl").name
    ...
    'pkg-1.0-py3-none-any.whl'

    ```
    """
    candidates = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not candidates:
        msg = f"No file matching '{pattern}' found in '{directory}' after the build"
        raise Exit(msg, code=1)
    return candidates[-1]


@task
def build(c: Context, check: bool = False) -> None:
    r"""Build the package and verify the built artifacts can be installed.

    The newest wheel and the newest source distribution in ``dist/`` are
    each installed in an isolated environment and the package is
    imported from it.

    Args:
        c: The invoke context.
        check: If True, also check the package's PyPI metadata with
            twine. Default is False.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    say(c, "📦 Building package...")
    c.run("uv build --clear", pty=True)
    say(c, "🔍 Verifying package installation...")
    for pattern in ("*.whl", "*.tar.gz"):
        artifact = _latest_artifact(Path("dist"), pattern)
        say(c, f"🔍 Verifying {artifact}...")
        c.run(
            f"uv run --isolated --no-project --with {shlex.quote(str(artifact))} -- "
            f"python -c {shlex.quote(f'import {name}')}",
            pty=True,
        )
    if check:
        say(c, "🔍 Checking package metadata with twine...")
        c.run("uvx twine check dist/*", pty=True)


@task
def pypi(c: Context) -> None:
    r"""Build and publish the package to PyPI.

    The token is read from the ``PYPI_TOKEN`` environment variable (or
    ``UV_PUBLISH_TOKEN``, which ``uv publish`` reads natively) and is
    passed to ``uv publish`` through its environment, so it does not
    appear on the command line. The task fails before building if no
    token is set. ``dist/`` is cleared by the build, so only the freshly
    built artifacts are uploaded.

    Raises:
        Exit: If neither ``PYPI_TOKEN`` nor ``UV_PUBLISH_TOKEN`` is set.
    """
    token = os.environ.get("PYPI_TOKEN") or os.environ.get("UV_PUBLISH_TOKEN")
    if not token:
        msg = "Set the PYPI_TOKEN (or UV_PUBLISH_TOKEN) environment variable to publish to PyPI"
        raise Exit(msg, code=1)
    build(c)
    say(c, "🚀 Publishing to PyPI...")
    c.run("uv publish", env={"UV_PUBLISH_TOKEN": token}, pty=True)
    say(c, "✅ Package published successfully")
