r"""Code and docstring formatting tasks.

Naming convention: ``check_<target>`` tasks are read-only (they fail
without modifying files); ``fix_<target>`` tasks modify files in place.
"""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import EXCLUDED_DIRS, get_config
from invoke_tasklib.output import say

if TYPE_CHECKING:
    from invoke.context import Context

SHELL_EXCLUDED_DIRS: frozenset[str] = EXCLUDED_DIRS | {"build", "dist", "site"}
r"""Directories whose shell scripts are never checked or formatted."""

_FIND_SH = (
    "find . \\( "
    + " -o ".join(f"-name {shlex.quote(d)}" for d in sorted(SHELL_EXCLUDED_DIRS))
    + " \\) -type d -prune -o -name '*.sh' -type f -print0"
)


@task
def check_python(c: Context) -> None:
    r"""Check code format with ruff without modifying files."""
    say(c, "🎨 Checking code format with ruff...")
    c.run("ruff format --check .", pty=True)
    say(c, "✅ Code format check passed")


@task
def check_docstrings(c: Context) -> None:
    r"""Check docstring formatting with docformatter without modifying
    files."""
    cfg = get_config(c)
    src = cfg["paths"]["src"]
    say(c, "📖 Checking docstring formatting...")
    c.run(f"docformatter --config ./pyproject.toml --check {src}", pty=True)
    say(c, "✅ Docstring format check passed")


@task
def fix_python(c: Context) -> None:
    r"""Format code in place with ruff.

    Note:
        This modifies files in place. Ensure your work is committed before
        running this task.
    """
    say(c, "🎨 Formatting code with ruff...")
    c.run("ruff format .", pty=True)
    say(c, "✅ Code formatting complete")


@task
def fix_docstrings(c: Context) -> None:
    r"""Format docstrings in source code with docformatter.

    Note:
        This modifies files in place. Ensure your work is committed before
        running this task.
    """
    cfg = get_config(c)
    src = cfg["paths"]["src"]
    say(c, "📖 Formatting docstrings...")
    c.run(f"docformatter --config ./pyproject.toml --in-place {src}", pty=True)
    say(c, "✅ Docstring formatting complete")


@task
def check_shell(c: Context) -> None:
    r"""Check shell scripts with shellcheck."""
    say(c, "🐚 Running shellcheck on shell scripts...")
    c.run(f"{_FIND_SH} | xargs -0 -r shellcheck --", pty=True)
    say(c, "✅ Shellcheck passed")


@task
def fix_shell(c: Context) -> None:
    r"""Format shell scripts in place with shfmt.

    Note:
        This modifies files in place. Ensure your work is committed before
        running this task.
    """
    say(c, "🔧 Running shfmt to format shell scripts...")
    c.run(f"{_FIND_SH} | xargs -0 -r shfmt -l -w --", pty=True)
    say(c, "✅ Shell formatting complete")
