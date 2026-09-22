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
def install(c: Context, optional_deps: bool = True, groups: str | None = None) -> None:
    r"""Install project dependencies and the package in editable mode.

    Args:
        c: The invoke context.
        optional_deps: If True, install all optional dependencies defined in
            the project extras. Default is True.
        groups: Comma-separated list of dependency groups to install, e.g.
            ``"dev,docs"``. Use an empty string to install no group. Defaults
            to the ``tasklib.groups.install`` config value (``"dev"`` unless
            overridden in ``invoke.yaml``).
    """
    if groups is None:
        groups = get_config(c)["groups"]["install"]
    logger.info("📦 Installing project dependencies...")
    cmd = ["uv sync --frozen"]
    if optional_deps:
        cmd.append("--all-extras")
    cmd.extend(f"--group {group}" for group in filter(None, (g.strip() for g in groups.split(","))))
    c.run(" ".join(cmd), pty=True)
    logger.info("🔧 Installing package in editable mode...")
    c.run("uv pip install -e .", pty=True)
    logger.info("✅ Installation complete")


@task
def update(c: Context, groups: str | None = None) -> None:
    r"""Update dependencies and pre-commit hooks to their latest
    versions.

    Args:
        c: The invoke context.
        groups: Comma-separated list of dependency groups to reinstall after
            updating, e.g. ``"dev,docs"``. Defaults to the
            ``tasklib.groups.update`` config value (``"dev,docs"`` unless
            overridden in ``invoke.yaml``).

    Warning:
        This may introduce breaking changes. Review the changes and run tests
        after updating.
    """
    if groups is None:
        groups = get_config(c)["groups"]["update"]
    logger.info("🔄 Updating dependencies...")
    c.run("uv sync --upgrade", pty=True)
    logger.info("🛠️  Upgrading uv tools...")
    c.run("uv tool upgrade --all", pty=True)
    logger.info("🪝 Updating pre-commit hooks...")
    c.run("pre-commit autoupdate", pty=True)
    logger.info(f"📦 Reinstalling with dependency groups: {groups}...")
    install(c, groups=groups)
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
