r"""Cleanup tasks."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import EXCLUDED_DIRS
from invoke_tasklib.output import say
from invoke_tasklib.runner import build_command, run

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


@task(
    name="all",
    default=True,
    help={"dry_run": "Print what would be removed, but remove nothing."},
)
def all_(c: Context, *, dry_run: bool = False) -> None:
    r"""Remove build artifacts and caches.

    The removed paths are ``dist``, ``build``, ``__pycache__``,
    ``.pytest_cache``, ``.coverage``, etc. The ``site`` directory is
    only removed if the project has a ``mkdocs.yml`` file, because that
    is what produces it. The ``*.egg-info`` directories are removed at
    the root and in ``src``.

    A top-level directory (``build``, ``dist``, ``site``, ...) that
    contains files tracked by git is kept, and the task says so.

    Args:
        c: The invoke context.
        dry_run: If True, print the paths that would be removed and
            remove nothing.
    """
    say(c, "🧹 Cleaning build artifacts and caches" + (" (dry run)..." if dry_run else "..."))
    dirs = [Path(d) for d in DIRS]
    if _has_mkdocs_config():
        dirs.append(Path(SITE_DIR))
    for d in dirs:
        _remove_dir(c, d, dry_run=dry_run, keep_tracked=True)
    for pattern in DIR_GLOBS:
        for p in sorted(Path().glob(pattern)):
            _remove_dir(c, p, dry_run=dry_run)
    for p in _find_pycache_dirs(Path()):
        _remove_dir(c, p, dry_run=dry_run)
    for f in FILES:
        _remove_file(c, Path(f), dry_run=dry_run)
    for pattern in FILE_GLOBS:
        for p in sorted(Path().glob(pattern)):
            _remove_file(c, p, dry_run=dry_run)
    say(c, _done_message(dry_run=dry_run))


@task(help={"dry_run": "Print what would be removed, but remove nothing."})
def pycache(c: Context, *, dry_run: bool = False) -> None:
    r"""Remove all __pycache__ directories.

    Args:
        c: The invoke context.
        dry_run: If True, print the paths that would be removed and
            remove nothing.
    """
    say(c, "🧹 Cleaning __pycache__ directories" + (" (dry run)..." if dry_run else "..."))
    for p in _find_pycache_dirs(Path()):
        _remove_dir(c, p, dry_run=dry_run)
    say(c, _done_message(dry_run=dry_run))


def _done_message(*, dry_run: bool) -> str:
    r"""Return the message that ends a cleanup.

    Args:
        dry_run: Whether nothing was removed.

    Returns:
        The message.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.clean import _done_message
    >>> _done_message(dry_run=True)
    '✅ Dry run complete: nothing was removed'

    ```
    """
    return "✅ Dry run complete: nothing was removed" if dry_run else "✅ Cleanup complete"


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


def _has_tracked_files(c: Context, path: Path) -> bool:
    r"""Check if git tracks a file in a path.

    The answer is ``False`` when git is not available or the directory
    is not in a repository: nothing can be said to be tracked then.

    Args:
        c: The invoke context.
        path: The directory (or file) to look at.

    Returns:
        ``True`` if ``git ls-files`` lists at least one file under it.
    """
    cmd = build_command("git ls-files --", default_paths=[str(path)])
    result = run(c, cmd, hide=True, warn=True, echo=False, check=False)
    return bool(result.ok and result.stdout.strip())


def _remove_dir(
    c: Context, path: Path, *, dry_run: bool = False, keep_tracked: bool = False
) -> None:
    r"""Remove a directory, if it exists.

    A symbolic link to a directory is removed as a link: the directory
    it points to is left untouched (``shutil.rmtree`` refuses a link).

    Args:
        c: The invoke context.
        path: The directory to remove.
        dry_run: If True, say that the directory would be removed and
            leave it.
        keep_tracked: If True, leave a directory that contains files
            tracked by git, and say so.
    """
    if not (path.is_symlink() or path.is_dir()):
        return
    if keep_tracked and _has_tracked_files(c, path):
        say(c, f"⏭️  Keeping {path}: it contains files tracked by git")
    elif dry_run:
        say(c, f"🗑️  Would remove {path}")
    elif path.is_symlink():
        say(c, f"🗑️  Removing {path}")
        path.unlink()
    else:
        say(c, f"🗑️  Removing {path}")
        shutil.rmtree(path)


def _remove_file(c: Context, path: Path, *, dry_run: bool = False) -> None:
    r"""Remove a file, if it exists.

    Args:
        c: The invoke context.
        path: The file to remove.
        dry_run: If True, say that the file would be removed and leave
            it.
    """
    if not path.is_file():
        return
    if dry_run:
        say(c, f"🗑️  Would remove {path}")
    else:
        say(c, f"🗑️  Removing {path}")
        path.unlink()
