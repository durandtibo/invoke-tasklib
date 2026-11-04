r"""Helpers to build the commands run by the tasks."""

from __future__ import annotations

import importlib.util
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

PROGRAM_HINTS: dict[str, str] = {
    "uv": "Install uv, see https://docs.astral.sh/uv/getting-started/installation/.",
    "shellcheck": (
        "Install shellcheck with your system package manager, for example "
        "`brew install shellcheck` or `apt install shellcheck`."
    ),
    "shfmt": (
        "Install shfmt with your system package manager, for example "
        "`brew install shfmt` or `apt install shfmt`."
    ),
    "uvx": "Install uv, which provides uvx, see https://docs.astral.sh/uv/getting-started/installation/.",
    "git": (
        "Install git with your system package manager, for example "
        "`brew install git` or `apt install git`, or on macOS `xcode-select --install`."
    ),
    "codespell": "Add codespell to the dependencies of the project, e.g. `uv add --dev codespell`.",
}
r"""How to install the programs that ``invoke env.install`` does not
install (or that it needs itself), by program name."""

PROGRAM_GROUPS: dict[str, str] = {
    "ruff": "dev",
    "ty": "dev",
    "pyright": "dev",
    "docformatter": "dev",
    "pre-commit": "dev",
    "pytest": "dev",
    "coverage": "dev",
    "xdoctest": "dev",
    "pytest_timeout": "dev",
    "pytest_cov": "dev",
    "mkdocs": "docs",
    "mike": "docs",
}
r"""The dependency group that provides a tool, by program or module
name, for the tools that are not in ``PROGRAM_HINTS``."""

DEFAULT_HINT = (
    "Install the project tools with `invoke env.install` (see the troubleshooting page of the "
    "documentation)."
)
r"""The hint of the programs that are in neither ``PROGRAM_HINTS`` nor
``PROGRAM_GROUPS``."""

_SEPARATORS = frozenset({"|", "||", "&&", ";", "&"})


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
    >>> build_command("ruff", args="-x", paths="src")
    'ruff -x src'

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


def _stages(command: str) -> list[list[str]]:
    r"""Split a command line into the commands of its pipeline.

    The command line is split on ``|``, ``||``, ``&&``, ``;`` and ``&``
    (outside quotes) and each part is split into words like a shell
    does.

    Args:
        command: The command line.

    Returns:
        The words of each command, without the empty ones.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import _stages
    >>> _stages("find . -name '*.sh' | xargs -0 shellcheck")
    [['find', '.', '-name', '*.sh'], ['xargs', '-0', 'shellcheck']]

    ```
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    stages: list[list[str]] = [[]]
    for token in lexer:
        if token in _SEPARATORS:
            stages.append([])
        else:
            stages[-1].append(token)
    return [words for words in stages if words]


def _program_of(words: Sequence[str]) -> str | None:
    r"""Return the program that a command really runs.

    ``xargs`` runs the command that follows its options, so that command
    is the one that has to be installed.

    Args:
        words: The words of a command.

    Returns:
        The program, or ``None`` if there is none (``xargs`` with no
        command).

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import _program_of
    >>> _program_of(["ruff", "check"])
    'ruff'
    >>> _program_of(["xargs", "-0", "-r", "shellcheck", "--"])
    'shellcheck'

    ```
    """
    if words[0] != "xargs":
        return words[0]
    return next((w for w in words[1:] if not w.startswith("-")), None)


def hint(program: str) -> str:
    r"""Return how to install a program.

    Args:
        program: The name of the program, or of the Python module.

    Returns:
        The entry of ``PROGRAM_HINTS`` for the program; else, if the
        program is in ``PROGRAM_GROUPS``, the command that installs its
        dependency group; else ``DEFAULT_HINT``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import hint
    >>> hint("uv")
    'Install uv, see https://docs.astral.sh/uv/getting-started/installation/.'
    >>> hint("mike")
    "Install it with the 'docs' group: `uv sync --group docs`."

    ```
    """
    if program in PROGRAM_HINTS:
        return PROGRAM_HINTS[program]
    group = PROGRAM_GROUPS.get(program)
    if group is None:
        return DEFAULT_HINT
    return f"Install it with the '{group}' group: `uv sync --group {group}`."


def _check_module(words: Sequence[str]) -> None:
    r"""Check the module of a ``python -m <module>`` command.

    Only the running interpreter is checked, because the availability of
    a module is looked up for this interpreter. Without this check, a
    missing module is reported by Python as ``No module named ...``,
    with no hint.

    Args:
        words: The words of a command.

    Raises:
        Exit: If the command runs a module of the running interpreter
            that is not installed.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import _check_module
    >>> _check_module(["ruff", "check"])

    ```
    """
    if len(words) < 3 or words[0] != sys.executable or words[1] != "-m":
        return
    module = words[2]
    if importlib.util.find_spec(module) is None:
        msg = f"The Python module '{module}' is not installed for {words[0]}. {hint(module)}"
        raise Exit(msg, code=127)


def check_program(command: str) -> None:
    r"""Check that the programs of a command are available.

    Every command of a pipeline (``a | b``, ``a && b``) is checked, and
    the command run by ``xargs`` is checked instead of ``xargs``. A
    program is not checked when it is an absolute path (for example the
    running interpreter, see ``python_executable``) or one of
    ``UNCHECKED_PROGRAMS``. For ``python -m <module>`` with the running
    interpreter, the module is checked.

    Args:
        command: The command line.

    Raises:
        Exit: If a program (or the module) is not found. The message
            says how to install it, see ``PROGRAM_HINTS``.

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
    for words in _stages(command):
        program = _program_of(words)
        if program is None or program.startswith("/") or program in UNCHECKED_PROGRAMS:
            _check_module(words)
            continue
        if shutil.which(program) is None:
            msg = f"'{program}' was not found on the PATH. {hint(program)}"
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
