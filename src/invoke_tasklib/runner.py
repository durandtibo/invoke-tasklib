r"""Helpers to build the commands run by the tasks."""

from __future__ import annotations

import shlex
import sys


def python_executable() -> str:
    r"""Return the shell-quoted path of the running Python interpreter.

    Tasks that run Python code or a Python module use this interpreter
    instead of the ``python`` found on the ``PATH``: the interpreter
    running Invoke is the one that has the project installed, and it
    works outside an activated virtual environment.

    Returns:
        The path of ``sys.executable``, quoted for the shell.

    Example usage:

    ```pycon
    >>> import sys
    >>> from invoke_tasklib.runner import python_executable
    >>> python_executable() == sys.executable
    True

    ```
    """
    return shlex.quote(sys.executable)
