r"""Discover the modules of a package without importing them.

It is run in a subprocess by ``imports.check-cycles``::

    python -m invoke_tasklib._discover <package>

and prints one module name per line.
"""

from __future__ import annotations

import importlib.util
import pkgutil
import sys
from pathlib import Path

IGNORED_MODULES = frozenset({"__main__"})


def discover_modules(name: str) -> list[str]:
    r"""Find a package and all its modules, without importing them.

    The package is located with ``importlib.util.find_spec`` and its
    submodules are found by walking the directories of the package, so
    no module code is executed. A cyclic import is therefore reported
    when each module is imported by the caller, not as a traceback during
    the discovery.

    Args:
        name: The name of the top-level package (or module).

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
    spec = importlib.util.find_spec(name)
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


def main(argv: list[str]) -> int:
    r"""Print the modules of the package given on the command line.

    Args:
        argv: The command line arguments, without the program name:
            the name of the package.

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
    if len(argv) != 1:
        sys.stderr.write("usage: python -m invoke_tasklib._discover <package>\n")
        return 2
    try:
        modules = discover_modules(argv[0])
    except ModuleNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write("\n".join(modules) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
