r"""Find the tools that the tasks run and say how to install them."""

from __future__ import annotations

import importlib.util
import re
import shlex
import shutil
import sys
from typing import TYPE_CHECKING

from invoke.exceptions import Exit

if TYPE_CHECKING:
    from collections.abc import Sequence


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
    "mkdocs": "docs",
    "mike": "docs",
}
r"""The dependency group that provides a program, by program name, for
the programs that are not in ``PROGRAM_HINTS``."""

MODULE_GROUPS: dict[str, str] = {
    "pytest": "dev",
    "coverage": "dev",
    "xdoctest": "dev",
    "pytest_timeout": "dev",
    "pytest_cov": "dev",
    "pytest_benchmark": "dev",
}
r"""The dependency group that provides a Python module, by name."""

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
    "--cov-branch": ("pytest_cov", "pytest-cov"),
    "--cov-config": ("pytest_cov", "pytest-cov"),
    "--no-cov": ("pytest_cov", "pytest-cov"),
    "--benchmark-only": ("pytest_benchmark", "pytest-benchmark"),
    "--benchmark-compare": ("pytest_benchmark", "pytest-benchmark"),
    "--benchmark-disable": ("pytest_benchmark", "pytest-benchmark"),
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


def hint(name: str, *, module: bool = False) -> str:
    r"""Return how to install a program or a Python module.

    Args:
        name: The name of the program, or of the Python module.
        module: If True, name is a Python module.

    Returns:
        The entry of PROGRAM_HINTS for the program; else the
        command that installs its dependency group, from
        PROGRAM_GROUPS (or MODULE_GROUPS for a module); else
        DEFAULT_HINT.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.tools import hint
    >>> hint("uv")
    'Install uv, see https://docs.astral.sh/uv/getting-started/installation/.'
    >>> hint("mike")
    "Install it with the 'docs' group: `uv sync --group docs`."
    >>> hint("pytest", module=True)
    "Install it with the 'dev' group: `uv sync --group dev`."

    ```
    """
    if not module and name in PROGRAM_HINTS:
        return PROGRAM_HINTS[name]
    group = (MODULE_GROUPS if module else PROGRAM_GROUPS).get(name)
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
    >>> from invoke_tasklib.tools import _check_plugin_options
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
    >>> from invoke_tasklib.tools import not_found_message
    >>> not_found_message("uv")[:36]
    "'uv' was not found on the PATH. Inst"

    ```
    """
    if module:
        return (
            f"The Python module '{name}' is not installed for "
            f"{interpreter or sys.executable}. {hint(name, module=True)}"
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
    if "/" in program or program in UNCHECKED_PROGRAMS:
        _check_module(words)
    elif shutil.which(program) is None:
        raise Exit(not_found_message(program), code=127)
