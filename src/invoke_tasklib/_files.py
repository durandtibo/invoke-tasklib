r"""Find the files of the project that a task works on."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from invoke_tasklib.config import EXCLUDED_DIRS

if TYPE_CHECKING:
    from collections.abc import Collection


def find_files(root: Path, suffix: str, excluded: Collection[str] = EXCLUDED_DIRS) -> list[Path]:
    r"""Find the files with a suffix under a root directory.

    The directories named in ``excluded`` (``.venv``, ``.git``, ...) are
    not walked into, at any depth, so a virtual environment or a build
    directory is never traversed. It needs no shell, ``find`` or
    ``xargs``.

    Args:
        root: The directory to search.
        suffix: The end of the file names, e.g. ``".md"``.
        excluded: The names of the directories to skip.

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
        dirnames[:] = [d for d in dirnames if d not in excluded]
        found.extend(Path(dirpath) / name for name in filenames if name.endswith(suffix))
    return sorted(found)
