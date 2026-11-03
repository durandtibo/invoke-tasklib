r"""Cleanup tasks."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.tasks import task

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
    ".tox",
    ".nox",
    ".hypothesis",
)
DIR_GLOBS = ("*.egg-info", "src/*.egg-info")
FILES = (".coverage", "coverage.xml")
FILE_GLOBS = (".coverage.*",)
SITE_DIR = "site"
MKDOCS_CONFIGS = ("mkdocs.yml", "docs/mkdocs.yml")


@task(name="all", default=True)
def all_(c: Context) -> None:
    r"""Remove build artifacts and caches.

    The removed paths are ``dist``, ``build``, ``__pycache__``,
    ``.pytest_cache``, ``.coverage``, etc. The ``site`` directory is
    only removed if the project has a ``mkdocs.yml`` file, because that
    is what produces it. The ``*.egg-info`` directories are removed at
    the root and in ``src``.
    """
    say(c, "🧹 Cleaning build artifacts and caches...")
    for d in DIRS:
        _remove_dir(c, Path(d))
    if _has_mkdocs_config():
        _remove_dir(c, Path(SITE_DIR))
    for pattern in DIR_GLOBS:
        for p in sorted(Path().glob(pattern)):
            _remove_dir(c, p)
    for p in _find_pycache_dirs(Path()):
        _remove_dir(c, p)
    for f in FILES:
        _remove_file(c, Path(f))
    for pattern in FILE_GLOBS:
        for p in sorted(Path().glob(pattern)):
            _remove_file(c, p)
    say(c, "✅ Cleanup complete")


@task
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
    ...     found = _find_pycache_dirs(Path(tmp))
    ...     [p.relative_to(tmp).as_posix() for p in found]
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


def _has_mkdocs_config() -> bool:
    r"""Check if the project builds documentation with MkDocs.

    Returns:
        ``True`` if one of ``MKDOCS_CONFIGS`` exists in the current
        directory, ``False`` otherwise.

    Example usage:

    ```pycon
    >>> import os
    >>> import tempfile
    >>> from invoke_tasklib.clean import _has_mkdocs_config
    >>> cwd = os.getcwd()
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     os.chdir(tmp)
    ...     found = _has_mkdocs_config()
    ...     os.chdir(cwd)
    ...
    >>> found
    False

    ```
    """
    return any(Path(config).is_file() for config in MKDOCS_CONFIGS)


def _remove_dir(c: Context, path: Path) -> None:
    r"""Remove a directory, if it exists.

    A symbolic link to a directory is removed as a link: the directory
    it points to is left untouched (``shutil.rmtree`` refuses a link).

    Args:
        c: The invoke context.
        path: The directory to remove.
    """
    if path.is_symlink():
        say(c, f"🗑️  Removing {path}")
        path.unlink()
    elif path.is_dir():
        say(c, f"🗑️  Removing {path}")
        shutil.rmtree(path)


def _remove_file(c: Context, path: Path) -> None:
    r"""Remove a file, if it exists.

    Args:
        c: The invoke context.
        path: The file to remove.
    """
    if path.is_file():
        say(c, f"🗑️  Removing {path}")
        path.unlink()
