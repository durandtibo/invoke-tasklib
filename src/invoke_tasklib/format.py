r"""Code and docstring formatting tasks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import get_config

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)


@task
def check_format(c: Context) -> None:
    r"""Check code format with ruff without modifying files."""
    logger.info("🎨 Checking code format with ruff...")
    c.run("ruff format --check .", pty=True)
    logger.info("✅ Code format check passed")


@task
def docformat(c: Context) -> None:
    r"""Format docstrings in source code with docformatter.

    Note:
        This modifies files in place. Ensure your work is committed before
        running this task.
    """
    cfg = get_config(c)
    src = cfg["paths"]["src"]
    logger.info("📖 Formatting docstrings...")
    c.run(f"docformatter --config ./pyproject.toml --in-place {src}", pty=True)
    logger.info("✅ Docstring formatting complete")


@task
def format_shell(c: Context) -> None:
    r"""Check and format shell scripts with shellcheck and shfmt."""
    find_sh = "find . -name '*.sh' -type f -not -path './.git/*'"
    logger.info("🐚 Running shellcheck on shell scripts...")
    c.run(f"{find_sh} -print0 | xargs -0 -r shellcheck --", pty=True)
    logger.info("✅ Shellcheck passed\n")

    logger.info("🔧 Running shfmt to format shell scripts...")
    c.run(f"{find_sh} -print0 | xargs -0 -r shfmt -l -w --", pty=True)
    logger.info("✅ Shell formatting complete")
