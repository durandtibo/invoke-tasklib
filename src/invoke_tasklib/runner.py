r"""Helpers to build the commands run by the tasks."""

from __future__ import annotations

import shlex
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from invoke.context import Context
    from invoke.runners import Result


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


def run(c: Context, command: str, **kwargs: Any) -> Result:
    r"""Run a command, echoing it and using a pty only on a terminal.

    All the tasks run their commands through this helper so that they
    behave alike:

    - the command line is echoed (``echo=True``) so that the user sees
      what is run, unless ``echo`` is passed explicitly;
    - a pseudo-terminal is used (``pty=True``) only if ``sys.stdout`` is
      a terminal or ``run.pty`` is set in the Invoke config. A pty keeps
      the colors of the tools but merges stderr into stdout and is not
      available everywhere (for example Windows or some CI sandboxes).

    Args:
        c: The invoke context.
        command: The command to run.
        **kwargs: Additional keyword arguments passed to ``c.run``. They
            take precedence over the defaults of this helper.

    Returns:
        The result of ``c.run``.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import MockContext
    >>> from invoke_tasklib.runner import run
    >>> c = MockContext(config=Config(), run=True)
    >>> _ = run(c, "ls")
    >>> c.run.call_args.kwargs["echo"]
    True

    ```
    """
    kwargs.setdefault("echo", True)
    kwargs.setdefault("pty", bool(c.config.run.pty) or sys.stdout.isatty())
    return c.run(command, **kwargs)
