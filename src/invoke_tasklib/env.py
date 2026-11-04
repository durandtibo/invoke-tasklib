r"""Environment and dependency management tasks."""

from __future__ import annotations

import importlib.util
import shlex
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.exceptions import Exit
from invoke.tasks import task

from invoke_tasklib.config import load_config
from invoke_tasklib.output import say
from invoke_tasklib.runner import hint, run

if TYPE_CHECKING:
    from invoke.context import Context

PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"


@task
def create_venv(c: Context) -> None:
    r"""Create a virtual environment and install invoke in it.

    Note:
        The virtual environment will be created in the .venv directory
        and any existing environment will be cleared. The task itself
        runs with ``invoke``, so ``invoke`` must already be available to
        run it.
    """
    cfg = load_config(c)
    python_version = cfg.package.python_version
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

    ``uv sync`` installs the project itself in editable mode, so no
    other command is needed.

    Args:
        c: The invoke context.
        optional_deps: If True, install all optional dependencies
            defined in the project extras. Default is True.
        groups: Comma-separated list of dependency groups to install,
            e.g. ``"dev,docs"``. Use an empty string to install no
            group. A group listed twice is installed once. Defaults to
            the ``tasklib.groups.install`` config value (``"dev"``
            unless overridden in ``invoke.yaml``).
    """
    if groups is None:
        groups = ",".join(load_config(c).groups.install)
    say(c, "📦 Installing project dependencies...")
    cmd = ["uv sync --locked"]
    if optional_deps:
        cmd.append("--all-extras")
    names = dict.fromkeys(filter(None, (g.strip() for g in groups.split(","))))
    cmd.extend(f"--group {shlex.quote(group)}" for group in names)
    run(c, " ".join(cmd))
    say(c, "✅ Installation complete")


@task(
    help={
        "groups": "Comma-separated dependency groups to reinstall (default: tasklib.groups.update)."
    }
)
def update(c: Context, groups: str | None = None) -> None:
    r"""Update dependencies and pre-commit hooks.

    The dependencies and the hooks are updated to their latest versions.
    The hooks are only updated if the project has a
    ``.pre-commit-config.yaml`` file. The ``uv`` tools installed on the
    machine are not touched: they are not part of the project.

    Args:
        c: The invoke context.
        groups: Comma-separated list of dependency groups to reinstall
            after updating, e.g. ``"dev,docs"``. Defaults to the
            ``tasklib.groups.update`` config value (``"dev,docs"``
            unless overridden in ``invoke.yaml``).

    Note:
        The lock file is upgraded first, then the environment is synced
        once with the dependency groups.

    Warning:
        This may introduce breaking changes. Review the changes and run
        tests after updating.
    """
    if groups is None:
        groups = ",".join(load_config(c).groups.update)
    say(c, "🔄 Updating dependencies...")
    run(c, "uv lock --upgrade")
    if Path(PRE_COMMIT_CONFIG).is_file():
        say(c, "🪝 Updating pre-commit hooks...")
        run(c, "pre-commit autoupdate")
    else:
        say(c, f"⏭️  No {PRE_COMMIT_CONFIG} file: skipping the pre-commit hooks")
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
    r"""Show the python configuration.

    ``command -v python`` is allowed to fail: it exits with 1 when no
    ``python`` is on the ``PATH``, which is not an error of the task.
    """
    say(c, "🐍 Python configuration:")
    run(c, "uv python list --only-installed")
    run(c, "uv python find")
    run(c, "command -v python", warn=True)


TOOL_PROGRAMS: tuple[str, ...] = (
    "uv",
    "uvx",
    "git",
    "ruff",
    "ty",
    "pyright",
    "docformatter",
    "codespell",
    "pre-commit",
    "shellcheck",
    "shfmt",
    "mkdocs",
    "mike",
)
r"""The programs that the tasks run, looked up on the ``PATH``."""

TOOL_MODULES: tuple[str, ...] = (
    "pytest",
    "coverage",
    "xdoctest",
    "pytest_timeout",
    "pytest_cov",
)
r"""The Python modules and pytest plugins that the tasks need."""


def _find_tool(name: str, *, module: bool = False) -> str | None:
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
    >>> from invoke_tasklib.env import _find_tool
    >>> _find_tool("no-such-program") is None
    True
    >>> _find_tool("no_such_module", module=True) is None
    True

    ```
    """
    if module:
        spec = importlib.util.find_spec(name)
        return None if spec is None else (spec.origin or name)
    return shutil.which(name)


@task
def check_tools(c: Context) -> None:
    r"""Check which tools of the tasks are available.

    Every program (``ruff``, ``ty``, ``pyright``, ``uv``, ...) and every
    Python module (``pytest``, ``coverage`` and the pytest plugins) that
    the tasks run is looked up, and one line per tool says where it was
    found, or how to install it. All the tools are listed, so one run
    shows everything that is missing. The config of the project is not
    needed, so the task can be run before anything is set up.

    Args:
        c: The invoke context.

    Raises:
        Exit: With the code 127 if a tool is missing.
    """
    say(c, "🧰 Checking the tools of the tasks...")
    lookups = [(name, False) for name in TOOL_PROGRAMS] + [(name, True) for name in TOOL_MODULES]
    missing: list[str] = []
    for name, module in lookups:
        found = _find_tool(name, module=module)
        if found is not None:
            say(c, f"✅ {name}: {found}")
            continue
        missing.append(name)
        kind = "Python module" if module else "program"
        say(c, f"❌ {name}: {kind} not found. {hint(name)}")
    if missing:
        msg = f"{len(missing)} of {len(lookups)} tool(s) missing: {', '.join(missing)}"
        raise Exit(msg, code=127)
    say(c, f"✅ All the {len(lookups)} tools are available")
