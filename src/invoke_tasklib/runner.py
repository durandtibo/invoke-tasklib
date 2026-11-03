r"""Helpers to build the commands run by the tasks."""

from __future__ import annotations

import shlex
import shutil
import sys
from typing import TYPE_CHECKING, Any

from invoke.exceptions import Exit

if TYPE_CHECKING:
    from collections.abc import Sequence

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


ARGS_HELP = 'Extra arguments for the tool, as one string, e.g. "-k foo -x".'
r"""Help of the ``--args`` option of the tasks."""

PATHS_HELP = "Files or directories to run on, as one string, instead of the default."
r"""Help of the ``--paths`` option of the tasks."""

UNCHECKED_PROGRAMS: frozenset[str] = frozenset({"command", "find"})
r"""First words of a command that are not looked up on the ``PATH``
(shell builtins and tools that every system has)."""


def build_command(
    program: str,
    *,
    args: str | None = None,
    paths: str | None = None,
    default_paths: Sequence[str] = (),
) -> str:
    r"""Build a command line from a program and the options of a task.

    Args:
        program: The program and its fixed arguments, e.g.
            ``"ruff check"``. It is used as it is (not quoted).
        args: Extra arguments of the user, as one string that is split
            like a shell does, e.g. ``"-k foo -x"``. They come after the
            fixed arguments.
        paths: Paths of the user, as one string that is split like a
            shell does. They replace ``default_paths``.
        default_paths: The paths used when ``paths`` is not set.

    Returns:
        The command line. The arguments and the paths are quoted when
        needed.

    Raises:
        Exit: If ``args`` or ``paths`` cannot be split (for example an
            unclosed quote).

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import build_command
    >>> build_command("ruff check", default_paths=["."])
    'ruff check .'
    >>> build_command("ruff check", args="--select E", paths="src tests", default_paths=["."])
    'ruff check --select E src tests'

    ```
    """
    words = [program, *_split(args, "--args"), *(_split(paths, "--paths") or default_paths)]
    return " ".join(words[:1] + [shlex.quote(w) for w in words[1:]])


def _split(value: str | None, option: str) -> list[str]:
    r"""Split the value of an option like a shell does.

    Args:
        value: The value, or ``None`` if the option is not set.
        option: The name of the option, used in the error message.

    Returns:
        The words of the value (empty if it is not set).

    Raises:
        Exit: If the value cannot be split, for example because of an
            unclosed quote.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import _split
    >>> _split('-k "a b" -x', "--args")
    ['-k', 'a b', '-x']
    >>> _split(None, "--args")
    []

    ```
    """
    if not value:
        return []
    try:
        return shlex.split(value)
    except ValueError as exc:
        msg = f"Cannot parse the value of {option} ({exc}): {value!r}"
        raise Exit(msg, code=2) from exc


def check_program(command: str) -> None:
    r"""Check that the program of a command is available.

    The program is the first word of the command. It is not checked when
    it is an absolute path (for example the running interpreter, see
    ``python_executable``) or one of ``UNCHECKED_PROGRAMS``.

    Args:
        command: The command line.

    Raises:
        Exit: If the program is not found on the ``PATH``. The message
            says how to install the project tools.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import check_program
    >>> check_program("find . -name '*.sh'")
    >>> check_program("no-such-program --version")
    Traceback (most recent call last):
        ...
    invoke.exceptions.Exit: ...

    ```
    """
    words = shlex.split(command)
    if not words or words[0].startswith("/") or words[0] in UNCHECKED_PROGRAMS:
        return
    if shutil.which(words[0]) is None:
        msg = (
            f"'{words[0]}' was not found on the PATH. Install the project tools with "
            "`invoke env.install` (see the troubleshooting page of the documentation)."
        )
        raise Exit(msg, code=127)


def run(c: Context, command: str, **kwargs: Any) -> Result:
    r"""Run a command, echoing it and using a pty only on a terminal.

    The program of the command must be on the ``PATH``, see
    ``check_program``.

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

    Raises:
        Exit: If the program of the command is not found.

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
    check_program(command)
    kwargs.setdefault("echo", True)
    kwargs.setdefault("pty", bool(c.config.run.pty) or sys.stdout.isatty())
    return c.run(command, **kwargs)
