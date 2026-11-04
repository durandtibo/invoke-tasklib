r"""Helpers to build and run the commands of the tasks."""

from __future__ import annotations

import shlex
import sys
from typing import TYPE_CHECKING, Any

from invoke.exceptions import Exit

from invoke_tasklib.tools import check_program

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


PATHS_HELP = (
    "Files or directories to run on, as one string, instead of the default "
    "(globs and ~ are passed as they are)."
)
r"""Help of the ``--paths`` option of the tasks."""


def build_command(
    program: str,
    *,
    args: str | None = None,
    paths: str | None = None,
    default_paths: Sequence[str] = (),
    args_option: str = "--args",
) -> str:
    r"""Build a command line from a program and the options of a task.

    Args:
        program: The program and its fixed arguments, e.g.
            ``"ruff check"``. It is used as it is (not quoted).
        args: Extra arguments of the user, as one string that is split
            like a shell does, e.g. ``"-k foo -x"``. They come after the
            fixed arguments.
        paths: Paths of the user, as one string that is split like a
            shell does. They replace ``default_paths``. A glob (``*``)
            or ``~`` is quoted, so the tool receives it as it is: it
            is up to the tool to expand a glob, and ``~`` is never
            expanded.
        default_paths: The paths used when ``paths`` is not set.
        args_option: The name of the option that ``args`` comes from,
            used in the error message (for a task that has more than
            one set of arguments, e.g. ``"--pyright-args"``).

    Returns:
        The command line. The arguments and the paths are quoted when
        needed, so the shell does not expand a glob, ``~`` or ``$VAR``.

    Raises:
        Exit: If ``args`` or ``paths`` cannot be split (for example an
            unclosed quote).

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import build_command
    >>> build_command("ruff check", default_paths=["."])
    'ruff check .'
    >>> build_command("ruff", args="-x", paths="src")
    'ruff -x src'
    >>> build_command("ruff", paths="*.py")
    "ruff '*.py'"

    ```
    """
    words = [
        program,
        *split_args(args, args_option),
        *(split_args(paths, "--paths") or default_paths),
    ]
    return " ".join(words[:1] + [shlex.quote(w) for w in words[1:]])


def split_args(value: str | None, option: str) -> list[str]:
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
    >>> from invoke_tasklib.runner import split_args
    >>> split_args('-k "a b" -x', "--args")
    ['-k', 'a b', '-x']
    >>> split_args(None, "--args")
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


def run(c: Context, command: str, *, check: bool = True, **kwargs: Any) -> Result:
    r"""Run a command, echoing it and using a pty only on a terminal.

    The program of the command must be on the ``PATH``, see
    ``check_program``. Pass ``check=False`` to skip that check when the
    caller knows better, for example for a command that is defined by a
    shell function or alias.

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
        check: If False, do not check that the program is available.
        **kwargs: Additional keyword arguments passed to ``c.run``. They
            take precedence over the defaults of this helper.

    Returns:
        The result of ``c.run``.

    Raises:
        Exit: If ``check`` is True and the program of the command is not
            found.

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
    if check:
        check_program(command)
    kwargs.setdefault("echo", True)
    kwargs.setdefault("pty", bool(c.config.run.pty) or sys.stdout.isatty())
    return c.run(command, **kwargs)


def capture(c: Context, command: str, *, warn: bool = False, check: bool = True) -> Result:
    r"""Run a command whose output the caller reads.

    It is ``run`` with the options that a command read by the code
    needs: the output is hidden (``hide=True``) and the command is not
    echoed (``echo=False``), and no pty is used (``pty=False``), so
    that stderr is not merged into stdout and a warning of the tool is
    never read as data.

    Args:
        c: The invoke context.
        command: The command to run.
        warn: If True, a command that fails does not raise: look at
            ``result.ok``.
        check: If False, do not check that the program is available,
            see ``run``.

    Returns:
        The result of ``c.run``, with the standard output in
        ``stdout``.

    Raises:
        Exit: If ``check`` is True and the program of the command is not
            found.
        UnexpectedExit: If the command fails and ``warn`` is False.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import MockContext
    >>> from invoke_tasklib.runner import capture
    >>> c = MockContext(config=Config(), run=True)
    >>> _ = capture(c, "ls")
    >>> c.run.call_args.kwargs["pty"]
    False

    ```
    """
    return run(c, command, check=check, hide=True, echo=False, pty=False, warn=warn)
