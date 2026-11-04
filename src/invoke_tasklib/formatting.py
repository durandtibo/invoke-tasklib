r"""Code and docstring formatting tasks.

Naming convention: ``check_<target>`` tasks are read-only (they fail
without modifying files); ``fix_<target>`` tasks modify files in place.
"""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import EXCLUDED_DIRS, load_config
from invoke_tasklib.output import step
from invoke_tasklib.runner import ARGS_HELP, PATHS_HELP, build_command, run

if TYPE_CHECKING:
    from invoke.context import Context

SHELL_EXCLUDED_DIRS: frozenset[str] = EXCLUDED_DIRS | {"build", "dist", "site"}
r"""Directories whose shell scripts are never checked or formatted."""

_FIND_SH = (
    "find . \\( "
    + " -o ".join(f"-name {shlex.quote(d)}" for d in sorted(SHELL_EXCLUDED_DIRS))
    + " \\) -type d -prune -o -name '*.sh' -type f -print0"
)


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


def _shell_command(tool: str, args: str | None, paths: str | None) -> str:
    r"""Build the command of a shell script tool.

    Args:
        tool: The program and its fixed options, e.g. ``"shellcheck"``.
        args: Extra arguments of the user, placed before ``--``.
        paths: Scripts of the user. If not set, the ``*.sh`` files
            found under the current directory (without
            ``SHELL_EXCLUDED_DIRS``) are used.

    Returns:
        The command line.

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
    return f"{_FIND_SH} | xargs -0 -r {base} --"


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def check_shell(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Check shell scripts with shellcheck.

    Args:
        c: The invoke context.
        args: Extra arguments passed to shellcheck.
        paths: The scripts to check instead of every ``*.sh`` file of
            the project.
    """
    with step(c, "🐚 Running shellcheck on shell scripts...", "✅ Shellcheck passed"):
        run(c, _shell_command("shellcheck", args, paths))


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
    with step(c, "🔧 Running shfmt to format shell scripts...", "✅ Shell formatting complete"):
        run(c, _shell_command("shfmt -l -w", args, paths))
