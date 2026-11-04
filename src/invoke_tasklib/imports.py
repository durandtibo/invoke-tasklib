r"""Import-graph tasks."""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from invoke.exceptions import Exit
from invoke.tasks import task

from invoke_tasklib._graph import find_cycles, import_graph, read_sources
from invoke_tasklib.config import load_config
from invoke_tasklib.output import report_failure, say
from invoke_tasklib.runner import python_executable, run

if TYPE_CHECKING:
    from invoke.context import Context


@task(
    help={
        "lazy": "Also follow the imports inside functions (run when called, not on import).",
        "type_checking": "Also follow the imports under `if TYPE_CHECKING:`.",
    }
)
def check_cycles(c: Context, *, lazy: bool = False, type_checking: bool = False) -> None:
    r"""Check for cyclic imports with a static import graph.

    The import graph of the package is built from the source files
    with ``ast``, without importing anything, and each cycle is
    printed as a path (``a -> b -> a``). Imports under ``if
    TYPE_CHECKING:`` and inside functions never run when a module is
    imported, so they are ignored unless asked. A syntax error or a
    missing optional dependency is not reported as a cycle.

    Args:
        c: The invoke context.
        lazy: If True, also follow the imports inside functions.
        type_checking: If True, also follow the imports under ``if
            TYPE_CHECKING:``.

    Raises:
        Exit: If the package cannot be found, a module cannot be
            parsed, or an import cycle is found.
    """
    name = load_config(c).package.import_name
    say(c, f"🔍 Building the import graph of {name}...")
    try:
        sources, packages = read_sources(name)
        graph = import_graph(sources, packages, lazy=lazy, type_checking=type_checking)
    except ModuleNotFoundError as exc:
        raise Exit(str(exc), code=1) from exc
    except SyntaxError as exc:
        msg = f"Cannot parse module {exc.filename}: {exc.msg} (line {exc.lineno})"
        raise Exit(msg, code=1) from exc
    cycles = find_cycles(graph)
    if cycles:
        lines = [f"  {' -> '.join(cycle)}" for cycle in cycles]
        msg = f"Found {len(cycles)} import cycle(s) in {name}:\n" + "\n".join(lines)
        raise Exit(msg, code=1)
    say(c, f"✅ No import cycle in {len(sources)} module(s)")


@task
def check_isolated(c: Context) -> None:
    r"""Check that every module imports on its own.

    Every module of the package (not only the subpackages) is discovered
    without being imported, then imported in its own interpreter. A
    module that fails to import on its own depends on something that is
    only initialized as a side effect of importing another module first,
    which is the usual symptom of a cyclic import. It also fails on a
    missing dependency or a syntax error, and it starts one interpreter
    per module, so it is slow for a package with heavy imports; see
    ``check_cycles`` for the static check.

    Raises:
        UnexpectedExit: If the discovery fails (for example the package
            cannot be found) or a module fails to import.
    """
    cfg = load_config(c)
    name = cfg.package.import_name
    python = python_executable()
    with report_failure(c, "🔍 Checking that each module imports on its own..."):
        say(c, f"🔍 Discovering modules of {name}...")
        discover = run(
            c, f"{python} -m invoke_tasklib._discover {shlex.quote(name)}", hide=True, echo=False
        )
        modules = [line for line in discover.stdout.splitlines() if line]
        say(c, f"🔍 Checking {len(modules)} module(s) one at a time...")
        for module in modules:
            say(c, f"🔍 Checking: {module}")
            run(c, f"{python} -c {shlex.quote(f'import {module}')}")
    say(c, f"✅ All {len(modules)} module(s) imported on their own")
