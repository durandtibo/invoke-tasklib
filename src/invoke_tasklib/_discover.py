r"""Discover the modules of a package without importing them.

It is run in a subprocess by ``imports.check-isolated``::

    python -m invoke_tasklib._discover <package>

and prints one module name per line, or::

    python -m invoke_tasklib._discover --import-each <package>

which imports every module in its own interpreter (the worker of
``imports.check-isolated``) and prints the number of modules, then one
line ``<module>\t<reason>`` for each module that fails to import.
"""

from __future__ import annotations

import asyncio
import importlib.machinery
import importlib.util
import pkgutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.machinery import ModuleSpec

IGNORED_MODULES = frozenset({"__main__"})


def find_spec(name: str) -> ModuleSpec | None:
    r"""Find the spec of a module, without importing anything.

    ``importlib.util.find_spec("a.b")`` imports ``a`` to read its
    ``__path__``. This function finds the top-level package with
    ``find_spec`` (which imports nothing) and each next part in the
    directories of the previous one, so a dotted name such as
    ``company.package`` does not run the code of ``company``.

    Args:
        name: The dotted name of the package or of the module.

    Returns:
        The spec, or ``None`` if the module cannot be found.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._discover import find_spec
    >>> find_spec("invoke_tasklib.config").name
    'invoke_tasklib.config'
    >>> find_spec("invoke_tasklib.no_such_module") is None
    True

    ```
    """
    first, *others = name.split(".")
    spec = importlib.util.find_spec(first)
    prefix = first
    for part in others:
        if spec is None or not spec.submodule_search_locations:
            return None
        prefix = f"{prefix}.{part}"
        spec = importlib.machinery.PathFinder.find_spec(
            prefix, list(spec.submodule_search_locations)
        )
    return spec


def discover_modules(name: str) -> list[str]:
    r"""Find a package and all its modules, without importing them.

    The package is located with ``find_spec`` (the parent of a dotted
    name is not imported either) and its
    submodules are found by walking the directories of the package, so
    no module code is executed. A cyclic import is therefore reported
    when each module is imported by the caller, not as a traceback
    during the discovery.

    Args:
        name: The name of the package (or module), dotted if it is in
            a namespace package, e.g. ``"company.package"``.

    Returns:
        The name of the package followed by the sorted names of all its
        submodules (modules and subpackages, recursively). ``__main__``
        modules are excluded because importing them can run a program.

    Raises:
        ModuleNotFoundError: If ``name`` cannot be found.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._discover import discover_modules
    >>> discover_modules("invoke_tasklib")[:2]
    ['invoke_tasklib', 'invoke_tasklib._discover']

    ```
    """
    spec = find_spec(name)
    if spec is None:
        msg = f"No module named '{name}'"
        raise ModuleNotFoundError(msg, name=name)
    modules = [name]
    if spec.submodule_search_locations:
        modules.extend(_walk(name, list(spec.submodule_search_locations)))
    return modules


def _walk(prefix: str, locations: list[str]) -> list[str]:
    r"""List the modules found in package directories, recursively.

    Args:
        prefix: The dotted name of the package that owns the
            directories.
        locations: The directories of the package.

    Returns:
        The sorted dotted names of the modules and subpackages found.

    Example usage:

    ```pycon
    >>> import tempfile
    >>> from pathlib import Path
    >>> from invoke_tasklib._discover import _walk
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     (Path(tmp) / "sub").mkdir()
    ...     _ = (Path(tmp) / "sub" / "__init__.py").write_text("")
    ...     _ = (Path(tmp) / "a.py").write_text("")
    ...     _walk("pkg", [tmp])
    ...
    ['pkg.a', 'pkg.sub']

    ```
    """
    found: list[str] = []
    for info in sorted(pkgutil.iter_modules(locations), key=lambda m: m.name):
        if info.name in IGNORED_MODULES:
            continue
        full_name = f"{prefix}.{info.name}"
        found.append(full_name)
        if info.ispkg:
            found.extend(_walk(full_name, [str(Path(loc) / info.name) for loc in locations]))
    return sorted(found)


MAX_WORKERS = 8
r"""The most interpreters that ``import_each`` runs at the same time."""


def _failure_reason(stderr: str, returncode: int) -> str:
    r"""Say why an import failed, in one line.

    Args:
        stderr: The standard error of the interpreter.
        returncode: Its exit code.

    Returns:
        The last line of the standard error (the exception of a
        traceback), or the exit code if there is none.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._discover import _failure_reason
    >>> _failure_reason("Traceback ...\nImportError: x\n", 1)
    'ImportError: x'
    >>> _failure_reason("", 3)
    'exit code 3'

    ```
    """
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else f"exit code {returncode}"


_IMPORT_CODE = "import importlib, sys; importlib.import_module(sys.argv[1])"
r"""The code of the interpreter that imports a module: the name of the
module is an argument, so it is never part of the code."""


async def _try_import(module: str, slots: asyncio.Semaphore) -> str | None:
    r"""Import a module in a new interpreter.

    Args:
        module: The dotted name of the module.
        slots: Limits the number of interpreters that run at once.

    Returns:
        ``None`` if the import succeeds, else the reason of the failure,
        see ``_failure_reason``.

    Example usage:

    ```pycon
    >>> import asyncio
    >>> from invoke_tasklib._discover import _try_import
    >>> async def main():
    ...     return await _try_import("json", asyncio.Semaphore(1))
    >>> asyncio.run(main()) is None
    True

    ```
    """

    async with slots:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            _IMPORT_CODE,
            module,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
    code = proc.returncode or 0
    return None if code == 0 else _failure_reason(stderr.decode(errors="replace"), code)


async def _try_import_all(modules: list[str], workers: int) -> list[str | None]:
    r"""Import every module in its own interpreter, a few at a time.

    Args:
        modules: The dotted names of the modules.
        workers: The most interpreters to run at the same time.

    Returns:
        The result of ``_try_import`` for each module, in order.

    Example usage:

    ```pycon
    >>> import asyncio
    >>> from invoke_tasklib._discover import _try_import_all
    >>> asyncio.run(_try_import_all(["json", "re"], 2))
    [None, None]

    ```
    """
    slots = asyncio.Semaphore(max(1, workers))
    return list(await asyncio.gather(*(_try_import(module, slots) for module in modules)))


def import_each(name: str, workers: int = MAX_WORKERS) -> tuple[int, list[tuple[str, str]]]:
    r"""Import every module of a package in its own interpreter.

    The modules are discovered without importing them, see
    ``discover_modules``. Each one is imported in a fresh interpreter,
    so a module that only works after another one was imported fails.
    Up to ``workers`` interpreters run at the same time, which is what
    makes the check fast for a large package.

    Args:
        name: The name of the package (or module).
        workers: The most interpreters to run at the same time.

    Returns:
        The number of modules, and a ``(module, reason)`` pair for each
        module that failed, in the order of the modules.

    Raises:
        ModuleNotFoundError: If ``name`` cannot be found.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._discover import import_each
    >>> import_each("invoke_tasklib._discover")
    (1, [])

    ```
    """
    modules = discover_modules(name)
    reasons = asyncio.run(_try_import_all(modules, workers))
    return len(modules), [(m, r) for m, r in zip(modules, reasons, strict=True) if r is not None]


def main(argv: list[str]) -> int:
    r"""Print the modules of the package given on the command line.

    With ``--import-each`` before the name, every module is imported in
    its own interpreter instead (see ``import_each``): the output is the
    number of modules, then ``<module>\t<reason>`` for each failure.
    The exit code is 0 even if modules failed: the caller reads the
    output.

    Args:
        argv: The command line arguments, without the program name:
            the name of the package, with ``--import-each`` before it
            to import the modules.

    Returns:
        The exit code: 0 on success, 2 if the arguments are invalid,
        1 if the package cannot be found.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._discover import main
    >>> _ = main(["invoke_tasklib"])  # doctest: +ELLIPSIS
    invoke_tasklib
    ...

    ```
    """
    each = argv[:1] == ["--import-each"]
    names = argv[1:] if each else argv
    if len(names) != 1:
        sys.stderr.write("usage: python -m invoke_tasklib._discover [--import-each] <package>\n")
        return 2
    try:
        if each:
            total, failures = import_each(names[0])
            lines = [str(total), *(f"{module}\t{reason}" for module, reason in failures)]
        else:
            lines = discover_modules(names[0])
    except ModuleNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
