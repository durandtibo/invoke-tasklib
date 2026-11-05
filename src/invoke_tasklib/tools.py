r"""Find the tools that the tasks run and say how to install them."""

from __future__ import annotations

import importlib.util
import os
import re
import shlex
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NamedTuple

from invoke.exceptions import Exit

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "TOOLS",
    "Tool",
    "check_program",
    "find_tool",
    "hint",
    "not_found_message",
    "tool_path",
]

_UNCHECKED_PROGRAMS: frozenset[str] = frozenset(
    {"command", "cd", "export", "test", "[", "exec", "source", ".", ":"}
)
r"""First words of a command that are not looked up on the ``PATH``
(shell builtins).

Some of them have an executable on some systems only (for example ``cd``
on macOS).
"""


class Tool(NamedTuple):
    r"""A program or a Python module that the tasks run.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.tools import Tool
    >>> Tool("ruff", group="dev").kind
    'program'

    ```
    """

    name: str
    r"""The name of the program, or of the module (``pytest_cov``)."""

    kind: Literal["program", "module"] = "program"
    r"""Whether the tool is looked up on the ``PATH`` or as a module."""

    group: str | None = None
    r"""The dependency group that provides the tool, if ``uv sync
    --group <group>`` installs it."""

    hint: str | None = None
    r"""How to install a tool that no group provides.

    It replaces the hint built from ``group``.
    """

    # The pytest options that the tool, a pytest plugin, provides.
    # The package to install is the module name with ``-`` instead of
    # ``_``.
    plugin_options: tuple[str, ...] = ()


_UV_URL = "https://docs.astral.sh/uv/getting-started/installation/"


def _system_hint(name: str, *, extra: str = "") -> str:
    r"""Build the hint of a program of the system package manager.

    Args:
        name: The name of the program.
        extra: A sentence added at the end.

    Returns:
        The hint.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.tools import _system_hint
    >>> _system_hint("jq")[:30]
    'Install jq with your system pa'

    ```
    """
    return (
        f"Install {name} with your system package manager, for example "
        f"`brew install {name}` or `apt install {name}`{extra}."
    )


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool("uv", hint=f"Install uv, see {_UV_URL}."),
        Tool("uvx", hint=f"Install uv, which provides uvx, see {_UV_URL}."),
        Tool(
            "git",
            hint=_system_hint("git", extra=", or on macOS `xcode-select --install`"),
        ),
        Tool("ruff", group="dev"),
        Tool("ty", group="dev"),
        Tool("pyright", group="dev"),
        Tool(
            "mypy",
            hint="Add mypy to the dependencies of the project, e.g. `uv add --dev mypy`.",
        ),
        Tool("docformatter", group="dev"),
        Tool(
            "codespell",
            hint="Add codespell to the dependencies of the project, e.g. `uv add --dev codespell`.",
        ),
        Tool("pre-commit", group="dev"),
        Tool("shellcheck", hint=_system_hint("shellcheck")),
        Tool("shfmt", hint=_system_hint("shfmt")),
        Tool("mkdocs", group="docs"),
        Tool("mike", group="docs"),
        Tool("pytest", "module", group="dev"),
        Tool("coverage", "module", group="dev"),
        Tool("xdoctest", "module", group="dev", plugin_options=("--xdoctest",)),
        Tool("pytest_timeout", "module", group="dev", plugin_options=("--timeout",)),
        Tool(
            "pytest_cov",
            "module",
            group="dev",
            plugin_options=(
                "--cov",
                "--cov-report",
                "--cov-append",
                "--cov-fail-under",
                "--cov-branch",
                "--cov-config",
                "--no-cov",
            ),
        ),
        Tool(
            "pytest_benchmark",
            "module",
            group="dev",
            plugin_options=("--benchmark-only", "--benchmark-compare", "--benchmark-disable"),
        ),
    )
}
r"""Every program and module that the tasks run, by name.

It is the one place to edit to add a tool: ``hint``,
``not_found_message``, ``env.check-tools`` and the check of the pytest
plugins read it. Names are unique across the programs and the
modules.
"""

_DEFAULT_HINT = (
    "Install the project tools with `invoke env.install` (see the troubleshooting page of the "
    "documentation)."
)
r"""The hint of a tool that is not in ``TOOLS``."""

_PLUGIN_OPTIONS: dict[str, tuple[str, str]] = {
    option: (tool.name, tool.name.replace("_", "-"))
    for tool in TOOLS.values()
    for option in tool.plugin_options
}
r"""The pytest options that come from a plugin, as a tuple of the module
and of the package to install, by option."""

_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def _strip_assignments(words: Sequence[str]) -> list[str]:
    r"""Remove the leading ``NAME=value`` words of a command.

    Args:
        words: The words of a command.

    Returns:
        The words from the first one that is not an assignment of an
        environment variable.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.tools import _strip_assignments
    >>> _strip_assignments(["FOO=1", "BAR=", "ruff", "check"])
    ['ruff', 'check']

    ```
    """
    start = 0
    while start < len(words) and _ASSIGNMENT.match(words[start]):
        start += 1
    return list(words[start:])


def hint(name: str) -> str:
    r"""Return how to install a program or a Python module.

    Args:
        name: The name of the program, or of the Python module.

    Returns:
        The ``hint`` of the tool in ``TOOLS``; else the command that
        installs its dependency group; else ``_DEFAULT_HINT`` (the tool
        is not in ``TOOLS``).

    Example usage:

    ```pycon
    >>> from invoke_tasklib.tools import hint
    >>> hint("uv")
    'Install uv, see https://docs.astral.sh/uv/getting-started/installation/.'
    >>> hint("mike")
    "Install it with the 'docs' group: `uv sync --group docs`."
    >>> hint("pytest")
    "Install it with the 'dev' group: `uv sync --group dev`."

    ```
    """
    tool = TOOLS.get(name)
    if tool is None:
        return _DEFAULT_HINT
    if tool.hint is not None:
        return tool.hint
    if tool.group is not None:
        return f"Install it with the '{tool.group}' group: `uv sync --group {tool.group}`."
    return _DEFAULT_HINT


def _check_plugin_options(words: Sequence[str]) -> None:
    r"""Check the pytest plugins of the options of a pytest command.

    Without this check, pytest reports a missing plugin as
    ``unrecognized arguments: --xdoctest``, which does not say what to
    install.

    Args:
        words: The words of the command, after ``python -m pytest``.

    Raises:
        Exit: If an option of ``_PLUGIN_OPTIONS`` is used and the module
            of its plugin is not installed.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.tools import _check_plugin_options
    >>> _check_plugin_options(["-x", "tests"])

    ```
    """
    for word in words:
        if word == "--":
            return
        option = word.partition("=")[0]
        if option not in _PLUGIN_OPTIONS:
            continue
        module, package = _PLUGIN_OPTIONS[option]
        if importlib.util.find_spec(module) is None:
            msg = (
                f"The option {option} needs the pytest plugin '{package}', which is not "
                f"installed for {sys.executable}. Add it to the dependencies of the project, "
                f"e.g. `uv add --dev {package}`."
            )
            raise Exit(msg, code=127)


def tool_path() -> str:
    r"""Return the ``PATH`` that the tasks use to find the programs.

    The directory of the running interpreter comes first: it is where
    ``uv sync`` installs the programs (``ruff``, ``ty``, ``mkdocs``,
    ...) of the virtual environment. Python modules are found with the
    running interpreter, so the programs of the same environment are
    found the same way, with no need to activate it. It also makes the
    task run the program of the environment, not another one that is
    earlier on the ``PATH``.

    Returns:
        The ``PATH`` of the process with the directory of
        ``sys.executable`` added to the front.

    Example usage:

    ```pycon
    >>> import os
    >>> from pathlib import Path
    >>> import sys
    >>> from invoke_tasklib.tools import tool_path
    >>> first = tool_path().split(os.pathsep)[0]
    >>> first == str(Path(sys.executable).parent)
    True

    ```
    """
    directories = [str(Path(sys.executable).parent)]
    directories.extend(filter(None, [os.environ.get("PATH")]))
    return os.pathsep.join(directories)


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
    >>> from invoke_tasklib.tools import not_found_message
    >>> not_found_message("uv")[:36]
    "'uv' was not found on the PATH or ne"

    ```
    """
    if module:
        return (
            f"The Python module '{name}' is not installed for "
            f"{interpreter or sys.executable}. {hint(name)}"
        )
    return f"'{name}' was not found on the PATH or next to the Python interpreter. {hint(name)}"


def _check_module(words: Sequence[str]) -> None:
    r"""Check the module of a ``python -m <module>`` command.

    Only the running interpreter is checked, because the availability of
    a module is looked up for this interpreter. Without this check, a
    missing module is reported by Python as ``No module named ...``,
    with no hint. For ``pytest``, the plugins of the options are checked
    too, see ``_PLUGIN_OPTIONS``.

    Args:
        words: The words of a command.

    Raises:
        Exit: If the command runs a module of the running interpreter
            that is not installed, or a pytest option whose plugin
            is not installed.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.tools import _check_module
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
    r"""Find a program on the tool path or a module of the interpreter.

    Args:
        name: The name of the program, or of the module.
        module: If True, look ``name`` up as a Python module of the
            running interpreter instead of as a program. A program is
            looked up in ``tool_path()``.

    Returns:
        The path of the program or of the module, or ``None`` if it is
        not available.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.tools import find_tool
    >>> find_tool("no-such-program") is None
    True
    >>> find_tool("no_such_module", module=True) is None
    True

    ```
    """
    if module:
        spec = importlib.util.find_spec(name)
        return None if spec is None else (spec.origin or name)
    return shutil.which(name, path=tool_path())


def check_program(command: str) -> None:
    r"""Check that the program of a command is available.

    Only the first word of the command is checked, after the
    ``NAME=value`` words that set environment variables. It is not
    checked when it is a path (for example the running interpreter, see
    ``python_executable``, or ``~/bin/tool``) or one of
    ``_UNCHECKED_PROGRAMS`` (the shell builtins). For
    ``python -m <module>`` with the running interpreter, the module is
    checked, and so are the plugins of the pytest options (see
    ``_PLUGIN_OPTIONS``).

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
            says how to install it, see ``hint``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.tools import check_program
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
    if "/" in program or program in _UNCHECKED_PROGRAMS:
        _check_module(words)
    elif shutil.which(program, path=tool_path()) is None:
        raise Exit(not_found_message(program), code=127)
