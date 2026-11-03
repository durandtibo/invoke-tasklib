r"""Cleanup tasks."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from invoke_tasklib.config import EXCLUDED_DIRS
from invoke_tasklib.output import say

if TYPE_CHECKING:
    from invoke.context import Context

DIRS = (
    "build",
    "dist",
    ".pytest_cache",
    ".ruff_cache",
    ".coverage_html",
    "htmlcov",
    ".benchmarks",
    ".mypy_cache",
    "site",
)
DIR_GLOBS = ("*.egg-info",)
FILES = (".coverage", "coverage.xml")


def all(c: Context) -> None:  # noqa: A001 (task name required by invoke)
    r"""Remove build artifacts and caches.

    The removed paths are ``dist``, ``build``, ``__pycache__``,
    ``.pytest_cache``, ``.coverage``, etc.
    """
    say(c, "🧹 Cleaning build artifacts and caches...")
    for d in DIRS:
        _remove_dir(c, Path(d))
    for pattern in DIR_GLOBS:
        for p in Path().glob(pattern):
            _remove_dir(c, p)
    for p in _find_pycache_dirs(Path()):
        _remove_dir(c, p)
    for f in FILES:
        _remove_file(c, Path(f))
    say(c, "✅ Cleanup complete")


def pycache(c: Context) -> None:
    r"""Remove all ``__pycache__`` directories."""
    say(c, "🧹 Cleaning __pycache__ directories...")
    for p in _find_pycache_dirs(Path()):
        _remove_dir(c, p)
    say(c, "✅ Cleanup complete")


def _find_pycache_dirs(root: Path) -> list[Path]:
    r"""Find the ``__pycache__`` directories under a root directory.

    The directories in ``EXCLUDED_DIRS`` (``.venv``, ``.git``,
    ``node_modules``, ...) are not walked into, so directories that the
    project does not own are never returned.

    Args:
        root: The directory to search.

    Returns:
        The sorted paths of the ``__pycache__`` directories found.

    Example usage:

    ```pycon
    >>> import tempfile
    >>> from pathlib import Path
    >>> from invoke_tasklib.clean import _find_pycache_dirs
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     (Path(tmp) / "pkg" / "__pycache__").mkdir(parents=True)
    ...     (Path(tmp) / ".venv" / "__pycache__").mkdir(parents=True)
    ...     [p.relative_to(tmp).as_posix() for p in _find_pycache_dirs(Path(tmp))]
    ...
    ['pkg/__pycache__']

    ```
    """
    found: list[Path] = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        if "__pycache__" in dirnames:
            dirnames.remove("__pycache__")
            found.append(Path(dirpath) / "__pycache__")
    return sorted(found)


def _remove_dir(c: Context, path: Path) -> None:
    if path.is_dir():
        say(c, f"🗑️  Removing {path}")
        shutil.rmtree(path)


def _remove_file(c: Context, path: Path) -> None:
    if path.is_file():
        say(c, f"🗑️  Removing {path}")
        path.unlink()
