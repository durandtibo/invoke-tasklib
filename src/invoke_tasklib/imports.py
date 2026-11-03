r"""Import-graph tasks."""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import get_config
from invoke_tasklib.output import say
from invoke_tasklib.runner import python_executable

if TYPE_CHECKING:
    from invoke.context import Context


@task
def check_cycles(c: Context) -> None:
    r"""Check for cyclic imports by importing each module in isolation.

    Every module of the package (not only the subpackages) is discovered
    without being imported, then imported in its own interpreter. A
    module that fails to import on its own depends on something that is
    only initialized as a side effect of importing another module first,
    which is the usual symptom of a cyclic import.

    Raises:
        UnexpectedExit: If the discovery fails (for example the package
            cannot be found) or a module fails to import.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    python = python_executable()
    say(c, f"🔍 Discovering modules of {name}...")
    discover = c.run(f"{python} -m invoke_tasklib._discover {shlex.quote(name)}", hide=True)
    modules = [line for line in discover.stdout.splitlines() if line]
    say(c, f"🔍 Checking {len(modules)} module(s) for cyclic imports...")
    for module in modules:
        say(c, f"🔍 Checking: {module}")
        c.run(f"{python} -c {shlex.quote(f'import {module}')}", pty=True)
    say(c, f"✅ All {len(modules)} module(s) imported without cyclic dependency errors")
