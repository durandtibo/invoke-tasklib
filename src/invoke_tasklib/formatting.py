r"""Code and docstring formatting tasks.

Naming convention: ``check_<target>`` tasks are read-only (they fail
without modifying files); ``fix_<target>`` tasks modify files in place.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib._files import find_files
from invoke_tasklib.config import EXCLUDED_DIRS, load_config
from invoke_tasklib.output import say, step
from invoke_tasklib.runner import ARGS_HELP, PATHS_HELP, build_command, run

if TYPE_CHECKING:
    from invoke.context import Context

# Directories whose shell scripts are never checked or formatted.
SHELL_EXCLUDED_DIRS: frozenset[str] = EXCLUDED_DIRS | {"build", "dist", "site"}


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def check_python(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Check code format with ruff without modifying files.

    Args:
        c: The invoke context.
        args: Extra arguments passed to ruff.
        paths: The files or directories to check instead of the whole
            project (``.``).
    """
    with step(c, "🎨 Checking code format with ruff...", "✅ Code format check passed"):
        run(c, build_command("ruff format --check", args=args, paths=paths, default_paths=["."]))


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def check_docstrings(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Check docstring format with docformatter.

    The files are not modified.

    Args:
        c: The invoke context.
        args: Extra arguments passed to docformatter.
        paths: The files or directories to check instead of
            ``paths.src``.
    """
    cfg = load_config(c)
    src = cfg.paths.src
    with step(c, "📖 Checking docstring formatting...", "✅ Docstring format check passed"):
        cmd = "docformatter --config ./pyproject.toml --check"
        run(c, build_command(cmd, args=args, paths=paths, default_paths=[src]))


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def fix_python(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Format code in place with ruff.

    Args:
        c: The invoke context.
        args: Extra arguments passed to ruff.
        paths: The files or directories to format instead of the whole
            project (``.``).

    Note:
        This modifies files in place. Ensure your work is committed
        before running this task.
    """
    with step(c, "🎨 Formatting code with ruff...", "✅ Code formatting complete"):
        run(c, build_command("ruff format", args=args, paths=paths, default_paths=["."]))


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def fix_docstrings(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Format docstrings in source code with docformatter.

    Args:
        c: The invoke context.
        args: Extra arguments passed to docformatter.
        paths: The files or directories to format instead of
            ``paths.src``.

    Note:
        This modifies files in place. Ensure your work is committed
        before running this task.
    """
    cfg = load_config(c)
    src = cfg.paths.src
    with step(c, "📖 Formatting docstrings...", "✅ Docstring formatting complete"):
        cmd = "docformatter --config ./pyproject.toml --in-place"
        run(c, build_command(cmd, args=args, paths=paths, default_paths=[src]))


def _shell_command(tool: str, args: str | None, paths: str | None) -> str | None:
    r"""Build the command of a shell script tool.

    Args:
        tool: The program and its fixed options, e.g. ``"shellcheck"``.
        args: Extra arguments of the user, placed before ``--``.
        paths: Scripts of the user. If not set, the ``*.sh`` files
            found under the current directory (without
            ``SHELL_EXCLUDED_DIRS``) are used.

    Returns:
        The command line, or ``None`` if there is no script to run the
        tool on.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.formatting import _shell_command
    >>> _shell_command("shellcheck", "-x", "a.sh")
    'shellcheck -x -- a.sh'

    ```
    """
    base = build_command(tool, args=args)
    if paths:
        return build_command(f"{base} --", paths=paths)
    scripts = [path.as_posix() for path in find_files(Path(), ".sh", SHELL_EXCLUDED_DIRS)]
    if not scripts:
        return None
    return build_command(f"{base} --", default_paths=scripts)


def _run_shell_tool(
    c: Context, tool: str, args: str | None, paths: str | None, messages: tuple[str, str]
) -> None:
    r"""Run a shell script tool, or say that there is no script.

    Args:
        c: The invoke context.
        tool: The program and its fixed options.
        args: Extra arguments of the user.
        paths: Scripts of the user.
        messages: The start and done messages of the step.
    """
    with step(c, *messages):
        command = _shell_command(tool, args, paths)
        if command is None:
            say(c, "⏭️  No shell script found: skipping")
        else:
            run(c, command)


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def check_shell(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Check shell scripts with shellcheck.

    Args:
        c: The invoke context.
        args: Extra arguments passed to shellcheck.
        paths: The scripts to check instead of every ``*.sh`` file of
            the project.
    """
    messages = ("🐚 Running shellcheck on shell scripts...", "✅ Shellcheck passed")
    _run_shell_tool(c, "shellcheck", args, paths, messages)


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def fix_shell(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Format shell scripts in place with shfmt.

    Args:
        c: The invoke context.
        args: Extra arguments passed to shfmt.
        paths: The scripts to format instead of every ``*.sh`` file of
            the project.

    Note:
        This modifies files in place. Ensure your work is committed
        before running this task.
    """
    messages = ("🔧 Running shfmt to format shell scripts...", "✅ Shell formatting complete")
    _run_shell_tool(c, "shfmt -l -w", args, paths, messages)
