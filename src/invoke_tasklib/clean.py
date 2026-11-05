r"""Cleanup tasks."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.exceptions import Exit
from invoke.tasks import task

from invoke_tasklib.config import EXCLUDED_DIRS, load_config
from invoke_tasklib.output import say
from invoke_tasklib.runner import build_command, capture
from invoke_tasklib.testing import coverage_outputs

if TYPE_CHECKING:
    from invoke.context import Context

NAMESPACE = "clean"
r"""The name of the namespace of the tasks of this module."""

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
_SITE_DIR_PATTERN = re.compile(r"^site_dir:[ \t]*(?P<value>[^#\n]*)", re.MULTILINE)


@task(
    name="all",
    default=True,
    help={"dry_run": "Print what would be removed, but remove nothing."},
)
def all_(c: Context, *, dry_run: bool = False) -> None:
    r"""Remove build artifacts and caches.

    The removed paths are ``dist``, ``build``, ``__pycache__``,
    ``.pytest_cache``, ``.coverage``, etc., and the HTML coverage
    report and the coverage files, from where they are written:
    the argument of ``tasklib.test.cov_reports`` (``html:cov_html``,
    ``xml:cov.xml``), else the options of ``[tool.coverage.*]`` in
    ``pyproject.toml``, else ``htmlcov`` and ``coverage.xml``. The
    ``site`` directory is only removed if the project has a MkDocs
    config file, because that is what produces it: the ``site_dir`` of
    ``paths.docs_config`` (relative to the config file, ``docs/site``
    by default), or ``site`` if the config is not valid. The
    ``*.egg-info`` directories are removed at the root and in ``src``.

    A directory outside the project, for example an absolute
    ``site_dir``, is never removed.

    A top-level directory (``build``, ``dist``, ``site``, ...) that
    contains files tracked by git is kept, and the task says so. So is
    a coverage file (``.coverage``, ``coverage.xml``, ...) that git
    tracks.

    Args:
        c: The invoke context.
        dry_run: If True, print the paths that would be removed and
            remove nothing.
    """
    say(c, "🧹 Cleaning build artifacts and caches" + (" (dry run)..." if dry_run else "..."))
    dirs = [Path(d) for d in DIRS]
    dirs.extend(_site_dirs(c))
    outputs = coverage_outputs(_cov_reports(c))
    html_dir = Path(outputs.html_dir)
    if html_dir not in dirs:
        dirs.append(html_dir)
    for d in dirs:
        _remove_dir(c, d, dry_run=dry_run, keep_tracked=True)
    for pattern in DIR_GLOBS:
        for p in sorted(Path().glob(pattern)):
            _remove_dir(c, p, dry_run=dry_run)
    for p in _find_pycache_dirs(Path()):
        _remove_dir(c, p, dry_run=dry_run)
    for f in dict.fromkeys((*FILES, *outputs.files)):
        _remove_file(c, Path(f), dry_run=dry_run, keep_tracked=True)
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


def _cov_reports(c: Context) -> tuple[str, ...]:
    r"""Return the coverage reports of the config.

    Args:
        c: The invoke context.

    Returns:
        The ``test.cov_reports`` value, or an empty tuple if the config
        is not valid (for example there is no ``package.name`` yet), so
        the default places are cleaned.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.clean import _cov_reports
    >>> _cov_reports(Context(config=Config()))
    ()

    ```
    """
    try:
        return load_config(c).test.cov_reports
    except Exit:
        return ()


def _site_dirs(c: Context) -> list[Path]:
    r"""Return the directories where MkDocs builds the site.

    The config file is ``paths.docs_config``. If the config is not
    valid (for example there is no ``package.name`` yet), the
    ``MKDOCS_CONFIGS`` files are used instead.

    Args:
        c: The invoke context.

    Returns:
        The ``site_dir`` of each config file that exists (``site`` if
        the file does not set it), relative to the directory of the
        config file. The list is empty if no config file exists.

    Example usage:

    ```pycon
    >>> import os
    >>> import tempfile
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.clean import _site_dirs
    >>> cwd = os.getcwd()
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     os.chdir(tmp)
    ...     found = _site_dirs(Context(config=Config()))
    ...     os.chdir(cwd)
    ...
    >>> found
    []

    ```
    """
    try:
        configs = [Path(load_config(c).paths.docs_config)]
    except Exit:
        configs = [Path(config) for config in MKDOCS_CONFIGS]
    return [config.parent / _read_site_dir(config) for config in configs if config.is_file()]


def _read_site_dir(config: Path) -> str:
    r"""Read the ``site_dir`` option of a MkDocs config file.

    The file is not parsed as YAML: the plain ``site_dir: value`` line
    is read, with or without quotes.

    Args:
        config: The path of the MkDocs config file.

    Returns:
        The value of ``site_dir``, or ``"site"`` if it is not set.

    Example usage:

    ```pycon
    >>> import tempfile
    >>> from pathlib import Path
    >>> from invoke_tasklib.clean import _read_site_dir
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     path = Path(tmp) / "mkdocs.yml"
    ...     _ = path.write_text("site_dir: 'public'  # output\n")
    ...     _read_site_dir(path)
    'public'

    ```
    """
    match = _SITE_DIR_PATTERN.search(config.read_text(encoding="utf-8"))
    value = match.group("value").strip().strip("'\"") if match else ""
    return value or SITE_DIR


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
    result = capture(c, cmd, warn=True, check=False)
    return bool(result.ok and result.stdout.strip())


def _is_inside_project(path: Path) -> bool:
    r"""Check that a path is inside the current directory.

    The directory that holds the path is resolved, so ``..`` and a
    link to the outside are seen. The last part is not resolved (unless
    it is ``.`` or ``..``): a link inside the project is removed as a
    link and its target is not touched.

    Args:
        path: The path to check, relative to the current directory or
            absolute.

    Returns:
        ``True`` if the path is below the current directory. The
        current directory itself is not inside the project.

    Example usage:

    ```pycon
    >>> from pathlib import Path
    >>> from invoke_tasklib.clean import _is_inside_project
    >>> _is_inside_project(Path("build"))
    True
    >>> _is_inside_project(Path("../build"))
    False
    >>> _is_inside_project(Path("."))
    False

    ```
    """
    root = Path.cwd().resolve()
    target = path.resolve() if path.name in {"", ".", ".."} else path.parent.resolve() / path.name
    return target != root and target.is_relative_to(root)


def _remove_dir(
    c: Context, path: Path, *, dry_run: bool = False, keep_tracked: bool = False
) -> None:
    r"""Remove a directory, if it exists.

    A symbolic link to a directory is removed as a link: the directory
    it points to is left untouched (``shutil.rmtree`` refuses a link).

    A directory outside the current directory (an absolute path, a
    path with ``..``) or the current directory itself is never removed:
    the task says so and goes on.

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
    if not _is_inside_project(path):
        say(c, f"⏭️  Not removing {path}: it is outside the project")
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


def _remove_file(
    c: Context, path: Path, *, dry_run: bool = False, keep_tracked: bool = False
) -> None:
    r"""Remove a file, if it exists.

    Args:
        c: The invoke context.
        path: The file to remove.
        dry_run: If True, say that the file would be removed and leave
            it.
        keep_tracked: If True, leave a file that is tracked by git, and
            say so.
    """
    if not path.is_file():
        return
    if keep_tracked and _has_tracked_files(c, path):
        say(c, f"⏭️  Keeping {path}: it is tracked by git")
    elif dry_run:
        say(c, f"🗑️  Would remove {path}")
    else:
        say(c, f"🗑️  Removing {path}")
        path.unlink()
