r"""Environment and dependency management tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import load_config
from invoke_tasklib.output import say
from invoke_tasklib.runner import run

if TYPE_CHECKING:
    from invoke.context import Context


@task
def create_venv(c: Context) -> None:
    r"""Create a virtual environment and install invoke in it.

    Note:
        The virtual environment will be created in the .venv directory and any
        existing environment will be cleared. The task itself runs with
        ``invoke``, so ``invoke`` must already be available to run it.
    """
    cfg = load_config(c)
    python_version = cfg["package"]["python_version"]
    say(c, f"🐍 Creating virtual environment with Python {python_version}...")
    run(c, f"uv venv --python {python_version} --clear")
    say(c, "📦 Installing invoke...")
    run(c, "uv pip install invoke")
    say(c, "✅ Virtual environment created successfully")


@task(
    help={
        "optional_deps": "Install all the optional dependencies (extras) of the project.",
        "groups": "Comma-separated dependency groups to install (default: tasklib.groups.install).",
    }
)
def install(c: Context, optional_deps: bool = True, groups: str | None = None) -> None:
    r"""Install the dependencies and the package (editable).

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
        groups = load_config(c)["groups"]["install"]
    say(c, "📦 Installing project dependencies...")
    cmd = ["uv sync --locked"]
    if optional_deps:
        cmd.append("--all-extras")
    cmd.extend(f"--group {group}" for group in filter(None, (g.strip() for g in groups.split(","))))
    run(c, " ".join(cmd))
    say(c, "🔧 Installing package in editable mode...")
    run(c, "uv pip install -e .")
    say(c, "✅ Installation complete")


@task(
    help={
        "groups": "Comma-separated dependency groups to reinstall (default: tasklib.groups.update)."
    }
)
def update(c: Context, groups: str | None = None) -> None:
    r"""Update dependencies and pre-commit hooks.

    The dependencies and the hooks are updated to their latest versions.

    Args:
        c: The invoke context.
        groups: Comma-separated list of dependency groups to reinstall after
            updating, e.g. ``"dev,docs"``. Defaults to the
            ``tasklib.groups.update`` config value (``"dev,docs"`` unless
            overridden in ``invoke.yaml``).

    Note:
        The lock file is upgraded first, then the environment is synced once
        with the dependency groups.

    Warning:
        This may introduce breaking changes. Review the changes and run tests
        after updating.
    """
    if groups is None:
        groups = load_config(c)["groups"]["update"]
    say(c, "🔄 Updating dependencies...")
    run(c, "uv lock --upgrade")
    say(c, "🛠️  Upgrading uv tools...")
    run(c, "uv tool upgrade --all")
    say(c, "🪝 Updating pre-commit hooks...")
    run(c, "pre-commit autoupdate")
    say(c, f"📦 Reinstalling with dependency groups: {groups}...")
    install(c, groups=groups)
    say(c, "✅ Update complete")


@task
def show_installed_packages(c: Context) -> None:
    r"""Show the installed packages."""
    say(c, "📦 Listing installed packages...")
    run(c, "uv pip list")


@task
def show_python_config(c: Context) -> None:
    r"""Show the python configuration."""
    say(c, "🐍 Python configuration:")
    run(c, "uv python list --only-installed")
    run(c, "uv python find")
    run(c, "command -v python")
