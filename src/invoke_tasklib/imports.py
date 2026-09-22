r"""Import-graph tasks."""

from __future__ import annotations

import logging
import shlex
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import get_config

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)


@task
def check_cycles(c: Context) -> None:
    r"""Check for cyclic import dependencies by importing each subpackage
    in isolation.

    Subpackages are discovered dynamically instead of relying on a hand-
    maintained list, so newly added subpackages are automatically
    covered.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    logger.info(f"🔍 Discovering subpackages of {name}...")
    discover_script = (
        "import importlib, pkgutil, sys\n"
        "name = sys.argv[1]\n"
        "package = importlib.import_module(name)\n"
        "names = [name] + sorted(\n"
        "    n for _, n, ispkg in pkgutil.walk_packages(package.__path__, prefix=f'{name}.')\n"
        "    if ispkg\n"
        ")\n"
        "print('\\n'.join(names))\n"
    )
    discover = c.run(f"python -c {shlex.quote(discover_script)} {name}", hide=True)
    modules = [line for line in discover.stdout.splitlines() if line]
    logger.info(f"🔍 Checking {len(modules)} module(s) for cyclic imports...")
    for module in modules:
        logger.info(f"🔍 Checking: {module}")
        c.run(f"python -c {shlex.quote(f'import {module}')}", pty=True)
    logger.info(f"✅ All {len(modules)} module(s) imported without cyclic dependency errors")
