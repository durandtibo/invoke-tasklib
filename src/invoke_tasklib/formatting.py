r"""Code and docstring formatting tasks.

Naming convention: ``check_<target>`` tasks are read-only (they fail
without modifying files); ``fix_<target>`` tasks modify files in place.
"""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import EXCLUDED_DIRS, load_config
from invoke_tasklib.output import say
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
def check_python(c: Context, args: str | None = None, paths: str | None = None) -> None:
    r"""Check code format with ruff without modifying files.

    Args:
        c: The invoke context.
        args: Extra arguments passed to ruff.
        paths: The files or directories to check instead of the whole
            project (``.``).
    """
    say(c, "🎨 Checking code format with ruff...")
    run(c, build_command("ruff format --check", args=args, paths=paths, default_paths=["."]))
    say(c, "✅ Code format check passed")


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def check_docstrings(c: Context, args: str | None = None, paths: str | None = None) -> None:
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
    say(c, "📖 Checking docstring formatting...")
    cmd = "docformatter --config ./pyproject.toml --check"
    run(c, build_command(cmd, args=args, paths=paths, default_paths=[src]))
    say(c, "✅ Docstring format check passed")


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def fix_python(c: Context, args: str | None = None, paths: str | None = None) -> None:
    r"""Format code in place with ruff.

    Args:
        c: The invoke context.
        args: Extra arguments passed to ruff.
        paths: The files or directories to format instead of the whole
            project (``.``).

    Note:
        This modifies files in place. Ensure your work is committed before
        running this task.
    """
    say(c, "🎨 Formatting code with ruff...")
    run(c, build_command("ruff format", args=args, paths=paths, default_paths=["."]))
    say(c, "✅ Code formatting complete")


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def fix_docstrings(c: Context, args: str | None = None, paths: str | None = None) -> None:
    r"""Format docstrings in source code with docformatter.

    Args:
        c: The invoke context.
        args: Extra arguments passed to docformatter.
        paths: The files or directories to format instead of
            ``paths.src``.

    Note:
        This modifies files in place. Ensure your work is committed before
        running this task.
    """
    cfg = load_config(c)
    src = cfg.paths.src
    say(c, "📖 Formatting docstrings...")
    cmd = "docformatter --config ./pyproject.toml --in-place"
    run(c, build_command(cmd, args=args, paths=paths, default_paths=[src]))
    say(c, "✅ Docstring formatting complete")


@task
def check_shell(c: Context) -> None:
    r"""Check shell scripts with shellcheck."""
    say(c, "🐚 Running shellcheck on shell scripts...")
    run(c, f"{_FIND_SH} | xargs -0 -r shellcheck --")
    say(c, "✅ Shellcheck passed")


@task
def fix_shell(c: Context) -> None:
    r"""Format shell scripts in place with shfmt.

    Note:
        This modifies files in place. Ensure your work is committed before
        running this task.
    """
    say(c, "🔧 Running shfmt to format shell scripts...")
    run(c, f"{_FIND_SH} | xargs -0 -r shfmt -l -w --")
    say(c, "✅ Shell formatting complete")
