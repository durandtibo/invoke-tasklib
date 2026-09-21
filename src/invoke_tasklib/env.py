r"""Environment and dependency management tasks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import get_config

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)


@task
def create_venv(c: Context) -> None:
    r"""Create a virtual environment and install invoke.

    Note:
        The virtual environment will be created in the .venv directory and any
        existing environment will be cleared.
    """
    cfg = get_config(c)
    python_version = cfg["package"]["python_version"]
    logger.info(f"🐍 Creating virtual environment with Python {python_version}...")
    c.run(f"uv venv --python {python_version} --clear", pty=True)
    logger.info("📦 Installing invoke...")
    c.run("uv tool install invoke", pty=True)
    logger.info("✅ Virtual environment created successfully")


@task
def install(
    c: Context, optional_deps: bool = True, dev_deps: bool = True, docs_deps: bool = False
) -> None:
    r"""Install project dependencies and the package in editable mode.

    Args:
        c: The invoke context.
        optional_deps: If True, install all optional dependencies defined in
            the project extras. Default is True.
        dev_deps: If True, install development dependencies. Default is True.
        docs_deps: If True, install documentation generation dependencies.
            Default is False.
    """
    logger.info("📦 Installing project dependencies...")
    cmd = ["uv sync --frozen"]
    if optional_deps:
        cmd.append("--all-extras")
    if dev_deps:
        cmd.append("--group dev")
    if docs_deps:
        cmd.append("--group docs")
    c.run(" ".join(cmd), pty=True)
    logger.info("🔧 Installing package in editable mode...")
    c.run("uv pip install -e .", pty=True)
    logger.info("✅ Installation complete")


@task
def update(c: Context) -> None:
    r"""Update dependencies and pre-commit hooks to their latest versions.

    Warning:
        This may introduce breaking changes. Review the changes and run tests
        after updating.
    """
    logger.info("🔄 Updating dependencies...")
    c.run("uv sync --upgrade", pty=True)
    logger.info("🛠️  Upgrading uv tools...")
    c.run("uv tool upgrade --all", pty=True)
    logger.info("🪝 Updating pre-commit hooks...")
    c.run("pre-commit autoupdate", pty=True)
    logger.info("📦 Reinstalling with docs dependencies...")
    install(c, docs_deps=True)
    logger.info("✅ Update complete")


@task
def show_installed_packages(c: Context) -> None:
    r"""Show the installed packages."""
    logger.info("📦 Listing installed packages...")
    c.run("uv pip list", pty=True)


@task
def show_python_config(c: Context) -> None:
    r"""Show the python configuration."""
    logger.info("🐍 Python configuration:")
    c.run("uv python list --only-installed", pty=True)
    c.run("uv python find", pty=True)
    c.run("which python", pty=True)
