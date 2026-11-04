r"""Helpers to build the commands run by the tasks."""

from __future__ import annotations

import importlib.util
import re
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

PATHS_HELP = (
    "Files or directories to run on, as one string, instead of the default "
    "(globs and ~ are passed as they are)."
)
r"""Help of the ``--paths`` option of the tasks."""

UNCHECKED_PROGRAMS: frozenset[str] = frozenset(
    {"command", "cd", "export", "test", "[", "exec", "source", ".", ":"}
)
r"""First words of a command that are not looked up on the ``PATH``
(shell builtins).

Some of them have an executable on some systems only (for example ``cd``
on macOS).
"""

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

PLUGIN_OPTIONS: dict[str, tuple[str, str]] = {
    "--xdoctest": ("xdoctest", "xdoctest"),
    "--timeout": ("pytest_timeout", "pytest-timeout"),
    "--cov": ("pytest_cov", "pytest-cov"),
    "--cov-report": ("pytest_cov", "pytest-cov"),
    "--cov-append": ("pytest_cov", "pytest-cov"),
    "--cov-fail-under": ("pytest_cov", "pytest-cov"),
    "--benchmark-only": ("pytest_benchmark", "pytest-benchmark"),
}
r"""The pytest options that come from a plugin, as a tuple of the module
and of the package to install, by option."""

_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


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


def _strip_assignments(words: Sequence[str]) -> list[str]:
    r"""Remove the leading ``NAME=value`` words of a command.

    Args:
        words: The words of a command.

    Returns:
        The words from the first one that is not an assignment of an
        environment variable.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import _strip_assignments
    >>> _strip_assignments(["FOO=1", "BAR=", "ruff", "check"])
    ['ruff', 'check']

    ```
    """
    start = 0
    while start < len(words) and _ASSIGNMENT.match(words[start]):
        start += 1
    return list(words[start:])


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


def _check_plugin_options(words: Sequence[str]) -> None:
    r"""Check the pytest plugins of the options of a pytest command.

    Without this check, pytest reports a missing plugin as
    ``unrecognized arguments: --xdoctest``, which does not say what to
    install.

    Args:
        words: The words of the command, after ``python -m pytest``.

    Raises:
        Exit: If an option of ``PLUGIN_OPTIONS`` is used and the module
            of its plugin is not installed.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import _check_plugin_options
    >>> _check_plugin_options(["-x", "tests"])

    ```
    """
    for word in words:
        if word == "--":
            return
        option = word.partition("=")[0]
        if option not in PLUGIN_OPTIONS:
            continue
        module, package = PLUGIN_OPTIONS[option]
        if importlib.util.find_spec(module) is None:
            msg = (
                f"The option {option} needs the pytest plugin '{package}', which is not "
                f"installed for {sys.executable}. Add it to the dependencies of the project, "
                f"e.g. `uv add --dev {package}`."
            )
            raise Exit(msg, code=127)


def not_found_message(name: str, *, module: bool = False, interpreter: str | None = None) -> str:
    r"""Build the message for a program or a module that is missing.

    Args:
        name: The name of the program, or of the Python module.
        module: If True, ``name`` is a Python module.
        interpreter: The interpreter the module is looked up for.
            Default is the running one.

    Returns:
        The message, with how to install the tool, see ``hint``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import not_found_message
    >>> not_found_message("uv")[:36]
    "'uv' was not found on the PATH. Inst"

    ```
    """
    if module:
        return (
            f"The Python module '{name}' is not installed for "
            f"{interpreter or sys.executable}. {hint(name)}"
        )
    return f"'{name}' was not found on the PATH. {hint(name)}"


def _check_module(words: Sequence[str]) -> None:
    r"""Check the module of a ``python -m <module>`` command.

    Only the running interpreter is checked, because the availability of
    a module is looked up for this interpreter. Without this check, a
    missing module is reported by Python as ``No module named ...``,
    with no hint. For ``pytest``, the plugins of the options are checked
    too, see ``PLUGIN_OPTIONS``.

    Args:
        words: The words of a command.

    Raises:
        Exit: If the command runs a module of the running interpreter
            that is not installed, or a pytest option whose plugin
            is not installed.

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
        raise Exit(not_found_message(module, module=True, interpreter=words[0]), code=127)
    if module == "pytest":
        _check_plugin_options(words[3:])


def find_tool(name: str, *, module: bool = False) -> str | None:
    r"""Find a program on the ``PATH`` or a module of the interpreter.

    Args:
        name: The name of the program, or of the module.
        module: If True, look ``name`` up as a Python module of the
            running interpreter instead of as a program.

    Returns:
        The path of the program or of the module, or ``None`` if it is
        not available.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import find_tool
    >>> find_tool("no-such-program") is None
    True
    >>> find_tool("no_such_module", module=True) is None
    True

    ```
    """
    if module:
        spec = importlib.util.find_spec(name)
        return None if spec is None else (spec.origin or name)
    return shutil.which(name)


def check_program(command: str) -> None:
    r"""Check that the program of a command is available.

    Only the first word of the command is checked, after the
    ``NAME=value`` words that set environment variables. It is not
    checked when it is a path (for example the running interpreter, see
    ``python_executable``, or ``~/bin/tool``) or one of
    ``UNCHECKED_PROGRAMS`` (the shell builtins). For
    ``python -m <module>`` with the running interpreter, the module is
    checked, and so are the plugins of the pytest options (see
    ``PLUGIN_OPTIONS``).

    The tasks run one program, so the rest of the command line is not
    parsed: a pipeline (``a | b``), a list (``a && b``), a subshell or
    a reserved word of the shell is not understood, and only its first
    word is looked up. To run such a command, pass ``check=False`` to
    ``run``. A command that cannot be split like a shell does (an
    unclosed quote) is not checked: the shell reports it.

    Args:
        command: The command line.

    Raises:
        Exit: If the program (or the module) is not found. The message
            says how to install it, see ``PROGRAM_HINTS``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.runner import check_program
    >>> check_program("cd docs")
    >>> check_program("no-such-program --version")
    Traceback (most recent call last):
        ...
    invoke.exceptions.Exit: ...

    ```
    """
    try:
        words = _strip_assignments(shlex.split(command))
    except ValueError:
        return
    if not words:
        return
    program = words[0]
    if "/" in program or program in UNCHECKED_PROGRAMS:
        _check_module(words)
    elif shutil.which(program) is None:
        raise Exit(not_found_message(program), code=127)


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
