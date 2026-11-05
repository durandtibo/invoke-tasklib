r"""Find the files of the project that a task works on.

A path of the config that does not exist is handled by one rule:

- A directory that the task may legitimately not have (the unit,
  integration and functional tests, the shell scripts): the task
  prints a ``⏭️`` line and exits with 0.
- A path that the task is about (``paths.src`` for the docstring and
  doctest tasks, ``paths.docs_config`` for the documentation): the task
  exits with 2 and the message names the key, see ``require_path``.
- The only input of a task that produces a measurement
  (``test.benchmark``): the task exits with 1.

A path given with ``--paths`` is never checked by the task: the tool
reports it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.exceptions import Exit

from invoke_tasklib.runner import build_command, capture

if TYPE_CHECKING:
    from invoke.context import Context

CACHE_DIRS: frozenset[str] = frozenset(
    {
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        ".nox",
        ".hypothesis",
        ".benchmarks",
        ".coverage_html",
    }
)
# The directories of the caches and reports of the tools: never the
# files of the project, even when git does not ignore them. ``clean``
# removes them.

OUTPUT_DIRS: frozenset[str] = frozenset({"build", "dist", "site", "htmlcov"})
# The directories of build outputs: generated, but a project may track
# files in them.

ENVIRONMENT_DIRS: frozenset[str] = frozenset({".git", ".venv", "node_modules"})
# The directories of environments: never the files of the project, even
# when git does not ignore them.

EXCLUDED_DIRS: frozenset[str] = CACHE_DIRS | OUTPUT_DIRS | ENVIRONMENT_DIRS
r"""The names of the directories that a walk of the file tree never
enters, at any depth (``find_files``, and ``clean`` for the
``__pycache__`` directories).

In a git work tree ``project_files`` lets git decide, so only the
directories of tools and environments (``CACHE_DIRS`` and
``ENVIRONMENT_DIRS``) are left out there: a tracked ``build/run.sh`` or
``site/index.md`` is returned.
"""

_IGNORED_PARTS: frozenset[str] = CACHE_DIRS | ENVIRONMENT_DIRS
# What ``project_files`` leaves out of the list of git.


def find_files(root: Path, suffix: str) -> list[Path]:
    r"""Find the files with a suffix under a root directory.

    The directories in ``EXCLUDED_DIRS`` (``.venv``, ``.git``,
    ``build``, ...) are not walked into, at any depth, so a virtual
    environment or a build directory is never traversed. It needs no
    shell, ``find`` or ``xargs``.

    Args:
        root: The directory to search.
        suffix: The end of the file names, e.g. ``".md"``.

    Returns:
        The sorted paths of the files found. They start with ``root``,
        so ``Path()`` gives paths without a prefix.

    Example usage:

    ```pycon
    >>> import tempfile
    >>> from pathlib import Path
    >>> from invoke_tasklib._files import find_files
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     (Path(tmp) / ".venv").mkdir()
    ...     _ = (Path(tmp) / "a.sh").write_text("")
    ...     _ = (Path(tmp) / ".venv" / "b.sh").write_text("")
    ...     found = find_files(Path(tmp), ".sh")
    ...     [p.relative_to(tmp).as_posix() for p in found]
    ...
    ['a.sh']

    ```
    """
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        found.extend(Path(dirpath) / name for name in filenames if name.endswith(suffix))
    return sorted(found)


def _in_git_work_tree(root: Path) -> bool:
    r"""Tell whether a directory is in a git work tree.

    The check looks for a ``.git`` entry (a directory, or a file for a
    worktree or a submodule) in the directory and its parents. It runs
    no command, so a project that is not a repository does not pay for
    a ``git`` call.

    Args:
        root: The directory to look at.

    Returns:
        ``True`` if the directory or one of its parents has a ``.git``
        entry.

    Example usage:

    ```pycon
    >>> from pathlib import Path
    >>> from invoke_tasklib._files import _in_git_work_tree
    >>> isinstance(_in_git_work_tree(Path()), bool)
    True

    ```
    """
    start = root.resolve()
    return any((directory / ".git").exists() for directory in (start, *start.parents))


def project_files(c: Context, root: Path, suffix: str) -> list[Path]:
    r"""Find the files of the project with a suffix under a directory.

    In a git work tree the files are the ones that git lists: the
    tracked files and the untracked files that are not ignored, so the
    rules of ``.gitignore`` are followed (like ``ruff``, ``codespell``
    and ``pre-commit`` do) and there is no list of directories to
    maintain. A tracked file that was deleted is left out, and so is a
    file in the directory of a tool or an environment (``.venv``,
    ``node_modules``, ...) that is not ignored. A tracked file in
    ``build`` or ``site`` is kept. Outside a git work tree, or without
    ``git``, the files are found by a walk, see ``find_files``, which
    skips every directory of ``EXCLUDED_DIRS``.

    Args:
        c: The invoke context.
        root: The directory to search.
        suffix: The end of the file names, e.g. ``".md"``.

    Returns:
        The sorted paths of the files found. They start with ``root``,
        so ``Path()`` gives paths without a prefix.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import MockContext
    >>> from invoke_tasklib._files import project_files
    >>> c = MockContext(config=Config(), run=True)
    >>> project_files(c, Path("no/such/dir"), ".sh")
    []

    ```
    """
    if not _in_git_work_tree(root):
        return find_files(root, suffix)
    pattern = f"*{suffix}" if root == Path() else f"{root.as_posix()}/*{suffix}"
    command = build_command(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--"],
        default_paths=[pattern],
    )
    result = capture(c, command, warn=True, check=False)
    if not result.ok:
        return find_files(root, suffix)
    found = (Path(name) for name in result.stdout.split("\0") if name)
    return sorted(
        path for path in found if path.is_file() and not _IGNORED_PARTS.intersection(path.parts)
    )


def require_path(path: str, key: str, *, file: bool = False) -> None:
    r"""Exit with the code 2 if a path of the config does not exist.

    Args:
        path: The path, relative to the working directory.
        key: The config key that sets the path, e.g.
            ``"tasklib.paths.src"``, named in the message.
        file: If True, the path must be a file (a directory is
            rejected too).

    Raises:
        Exit: If the path does not exist (code 2).

    Example usage:

    ```pycon
    >>> from invoke_tasklib._files import require_path
    >>> require_path(".", "tasklib.paths.src")
    >>> require_path("no/dir", "tasklib.paths.src")
    Traceback (most recent call last):
        ...
    invoke.exceptions.Exit: 'no/dir' (tasklib.paths.src) does not ...

    ```
    """
    target = Path(path)
    if not (target.is_file() if file else target.exists()):
        msg = f"'{path}' ({key}) does not exist: set it in invoke.yaml"
        raise Exit(msg, code=2)
