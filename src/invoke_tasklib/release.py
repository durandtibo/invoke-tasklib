r"""Build and publish tasks (PyPI package)."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.exceptions import Exit
from invoke.tasks import task

from invoke_tasklib.config import load_config
from invoke_tasklib.output import say
from invoke_tasklib.runner import ARGS_HELP, build_command, run

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


@task(help={"check": "Also check the package metadata with twine.", "args": ARGS_HELP})
def build(c: Context, check: bool = False, args: str | None = None) -> None:
    r"""Build the package and verify the built artifacts.

    The artifacts are checked to be installable. The newest wheel and
    the newest source distribution in ``dist/`` are each installed in an
    isolated environment and the package is imported from it, using
    ``package.import_name``.

    Args:
        c: The invoke context.
        check: If True, also check the package's PyPI metadata with
            twine. Default is False.
        args: Extra arguments passed to ``uv build``.
    """
    cfg = load_config(c)
    import_name = cfg.package.import_name
    say(c, "📦 Building package...")
    run(c, build_command("uv build --clear", args=args))
    say(c, "🔍 Verifying package installation...")
    for pattern in ("*.whl", "*.tar.gz"):
        artifact = _latest_artifact(Path("dist"), pattern)
        say(c, f"🔍 Verifying {artifact}...")
        run(
            c,
            f"uv run --isolated --no-project --with {shlex.quote(str(artifact))} -- "
            f"python -c {shlex.quote(f'import {import_name}')}",
        )
    if check:
        say(c, "🔍 Checking package metadata with twine...")
        run(c, "uvx twine check dist/*")


@task(help={"args": ARGS_HELP})
def pypi(c: Context, args: str | None = None) -> None:
    r"""Build and publish the package to PyPI.

    The token is read from the ``PYPI_TOKEN`` environment variable (or
    ``UV_PUBLISH_TOKEN``, which ``uv publish`` reads natively) and is
    passed to ``uv publish`` through its environment, so it does not
    appear on the command line. The task fails before building if no
    token is set. ``dist/`` is cleared by the build, so only the freshly
    built artifacts are uploaded.

    Args:
        c: The invoke context.
        args: Extra arguments passed to ``uv publish``, e.g.
            ``"--index testpypi"``.

    Raises:
        Exit: If neither ``PYPI_TOKEN`` nor ``UV_PUBLISH_TOKEN`` is set.
    """
    token = os.environ.get("PYPI_TOKEN") or os.environ.get("UV_PUBLISH_TOKEN")
    if not token:
        msg = "Set the PYPI_TOKEN (or UV_PUBLISH_TOKEN) environment variable to publish to PyPI"
        raise Exit(msg, code=1)
    build(c)
    say(c, "🚀 Publishing to PyPI...")
    run(c, build_command("uv publish", args=args), env={"UV_PUBLISH_TOKEN": token})
    say(c, "✅ Package published successfully")
