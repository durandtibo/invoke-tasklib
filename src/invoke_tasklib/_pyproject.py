r"""Read the ``pyproject.toml`` file of the project."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from invoke.exceptions import Exit

_POSITION = re.compile(r"^(?P<reason>.*) \(at line (?P<line>\d+), column (?P<column>\d+)\)$")


def _describe_error(exc: tomllib.TOMLDecodeError) -> str:
    r"""Describe a TOML parse error with its position.

    Args:
        exc: The error raised by ``tomllib``.

    Returns:
        ``"(line 12, column 5): Invalid value"`` when the error has a
        position, else the message of the parser alone.

    Example usage:

    ```pycon
    >>> import tomllib
    >>> from invoke_tasklib._pyproject import _describe_error
    >>> try:
    ...     tomllib.loads("[project\n")
    ... except tomllib.TOMLDecodeError as exc:
    ...     print(_describe_error(exc))
    (line 1, column 9): Expected ']' at the end of a table declaration

    ```
    """
    match = _POSITION.match(str(exc))
    if match is None:
        return str(exc)
    return f"(line {match['line']}, column {match['column']}): {match['reason']}"


def read_pyproject(path: Path = Path("pyproject.toml")) -> dict[str, Any]:
    r"""Read a ``pyproject.toml`` file.

    Args:
        path: The path of the file.

    Returns:
        The content of the file, or an empty dict if it does not exist.

    Raises:
        Exit: If the file cannot be parsed as TOML (code 1). The
            message names the file, the line and the column of the
            error, and the reason given by the parser.

    Example usage:

    ```pycon
    >>> from pathlib import Path
    >>> from invoke_tasklib._pyproject import read_pyproject
    >>> read_pyproject(Path("no/such/pyproject.toml"))
    {}

    ```
    """
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        where = _describe_error(exc)
        msg = f"invalid TOML in '{path}' {where}. Fix the file and run the task again."
        raise Exit(msg, code=1) from exc
