r"""Code and docstring formatting tasks.

Naming convention: ``check_<target>`` tasks are read-only (they fail
without modifying files); ``fix_<target>`` tasks modify files in place.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib._files import project_files, require_path
from invoke_tasklib.config import load_config
from invoke_tasklib.output import say, step
from invoke_tasklib.runner import ARGS_HELP, PATHS_HELP, build_command, run

if TYPE_CHECKING:
    from invoke.context import Context

# The name of the namespace of the tasks of this module.
NAMESPACE = "format"


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

    Raises:
        Exit: With the code 2 if ``paths`` is not set and
            ``paths.src`` does not exist.
    """
    cfg = load_config(c)
    src = cfg.paths.src
    if paths is None:
        require_path(src, "tasklib.paths.src")
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

    Raises:
        Exit: With the code 2 if ``paths`` is not set and
            ``paths.src`` does not exist.

    Note:
        This modifies files in place. Ensure your work is committed
        before running this task.
    """
    cfg = load_config(c)
    src = cfg.paths.src
    if paths is None:
        require_path(src, "tasklib.paths.src")
    with step(c, "📖 Formatting docstrings...", "✅ Docstring formatting complete"):
        cmd = "docformatter --config ./pyproject.toml --in-place"
        run(c, build_command(cmd, args=args, paths=paths, default_paths=[src]))


def _shell_command(c: Context, tool: str, args: str | None, paths: str | None) -> str | None:
    r"""Build the command of a shell script tool.

    Args:
        c: The invoke context.
        tool: The program and its fixed options, e.g. ``"shellcheck"``.
        args: Extra arguments of the user, placed before ``--``.
        paths: Scripts of the user. If not set, the ``*.sh`` files
            of the project are used (see ``project_files``; outside a
            git work tree, the walk skips ``EXCLUDED_DIRS``).

    Returns:
        The command line, or ``None`` if there is no script to run the
        tool on.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import MockContext
    >>> from invoke_tasklib.formatting import _shell_command
    >>> c = MockContext(config=Config(), run=True)
    >>> _shell_command(c, "shellcheck", "-x", "a.sh")
    'shellcheck -x -- a.sh'

    ```
    """
    base = build_command(tool, args=args)
    if paths:
        return build_command(f"{base} --", paths=paths)
    scripts = [path.as_posix() for path in project_files(c, Path(), ".sh")]
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
        command = _shell_command(c, tool, args, paths)
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
def check_shell_format(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Check the format of shell scripts with shfmt.

    It is the read-only counterpart of ``format.fix-shell``: ``shfmt
    -d`` prints a diff and fails if a script would be reformatted,
    but never changes a file.

    Args:
        c: The invoke context.
        args: Extra arguments passed to shfmt.
        paths: The scripts to check instead of every ``*.sh`` file of
            the project.
    """
    messages = ("🔎 Running shfmt on shell scripts...", "✅ Shell format is correct")
    _run_shell_tool(c, "shfmt -d", args, paths, messages)


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
