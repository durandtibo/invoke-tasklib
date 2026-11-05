r"""Import-graph tasks."""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from invoke.exceptions import Exit
from invoke.tasks import task

from invoke_tasklib._graph import find_cycles, import_graph, read_sources
from invoke_tasklib.config import load_config
from invoke_tasklib.output import report_failure, say
from invoke_tasklib.runner import capture, python_executable

if TYPE_CHECKING:
    from invoke.context import Context


NAMESPACE = "imports"
r"""The name of the namespace of the tasks of this module."""


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


def _parse_import_each(stdout: str) -> tuple[int, list[tuple[str, str]]]:
    r"""Read the output of the ``_discover --import-each`` worker.

    Args:
        stdout: The first line is the number of modules, then there is
            a ``<module>\t<reason>`` line for each module that failed.

    Returns:
        The number of modules, and the ``(module, reason)`` pairs.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.imports import _parse_import_each
    >>> _parse_import_each("3\na.b\tImportError: x\n")
    (3, [('a.b', 'ImportError: x')])

    ```
    """
    first, *rest = stdout.splitlines() or ["0"]
    failures = [tuple(line.split("\t", 1)) for line in rest if line]
    return int(first), [(module, reason) for module, reason in failures]


@task
def check_isolated(c: Context) -> None:
    r"""Check that every module imports on its own.

    Every module of the package (not only the subpackages) is discovered
    without being imported, then imported in its own interpreter. A
    module that fails to import on its own depends on something that is
    only initialized as a side effect of importing another module first,
    which is the usual symptom of a cyclic import. It also fails on a
    missing dependency or a syntax error. It starts one interpreter per
    module, a few at a time, so it is slow for a package with heavy
    imports; see ``check_cycles`` for the static check.

    One worker (``python -m invoke_tasklib._discover --import-each``)
    does the discovery and starts the interpreters, so the task runs a
    single command whatever the size of the package.

    The package that is checked is the one that the running
    interpreter finds: the installed (editable) package, or the one in
    the current directory for a flat layout. It is the source tree,
    not a built artifact, which ``release.build`` checks in isolated
    mode.

    The output is one line per step and one line per module that
    fails, with the last line of its traceback, then the summary. The
    commands are not echoed, so a package of 300 modules does not
    write 300 lines.

    Raises:
        UnexpectedExit: If the discovery fails (for example the package
            cannot be found).
        Exit: If a module fails to import on its own (code 1). Every
            module is tried, and all the failures are listed.
    """
    cfg = load_config(c)
    name = cfg.package.import_name
    python = python_executable()
    with report_failure(c, "🔍 Checking that each module imports on its own..."):
        say(c, f"🔍 Importing each module of {name} in its own interpreter...")
        command = f"{python} -m invoke_tasklib._discover --import-each {shlex.quote(name)}"
        total, failures = _parse_import_each(capture(c, command).stdout)
        for module, reason in failures:
            say(c, f"❌ {module}: {reason}", err=True)
        if failures:
            msg = f"{len(failures)} of {total} module(s) failed to import on their own"
            raise Exit(msg, code=1)
    say(c, f"✅ All {total} module(s) imported on their own")
