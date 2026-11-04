r"""Default values of the config that are derived from the project."""

from __future__ import annotations

from pathlib import Path

from invoke_tasklib.config._constants import TEST_SCOPES
from invoke_tasklib.config._validate import _validate_import_name


def _default_src(import_name: str) -> str:
    r"""Return the default source directory of a package.

    The ``src`` layout (``src/<import_name>``) is used unless only the
    flat layout (``<import_name>`` at the project root) exists on disk.

    Args:
        import_name: The import name of the package.

    Returns:
        ``"<import_name>"`` if that directory exists and
        ``src/<import_name>`` does not, ``"src/<import_name>"``
        otherwise.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._derive import _default_src
    >>> _default_src("no_such_package")
    'src/no_such_package'

    ```
    """
    src_layout = f"src/{import_name}"
    if not Path(src_layout).is_dir() and Path(import_name).is_dir():
        return import_name
    return src_layout


def _derive_defaults(merged: dict[str, dict[str, object]]) -> None:
    r"""Fill the values of the config that are derived from others.

    Args:
        merged: The values of each section, defaults and user values
            merged. ``package.name`` must be a valid string. It is
            changed in place: ``package.import_name``, ``paths.src`` and
            the paths of the test scopes that are not set get their
            default.

    Raises:
        ValueError: If ``package.import_name`` is not a Python module
            name (and ``paths.src`` has to be derived from it).

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._derive import _derive_defaults
    >>> package = {"name": "my-pkg", "import_name": None}
    >>> paths = {"src": "src", "tests": "tests", "unit_tests": None}
    >>> paths.update(integration_tests="i", functional_tests="f")
    >>> paths["benchmarks"] = "b"
    >>> merged = {"package": package, "paths": paths}
    >>> _derive_defaults(merged)
    >>> merged["package"]["import_name"]
    'my_pkg'
    >>> merged["paths"]["unit_tests"]
    'tests/unit'

    ```
    """
    package, paths = merged["package"], merged["paths"]
    if package["import_name"] is None:
        package["import_name"] = str(package["name"]).replace("-", "_")
    if paths["src"] is None:
        paths["src"] = _default_src(_validate_import_name(package["import_name"]))
    for key, scope in TEST_SCOPES.items():
        if paths[key] is None:
            paths[key] = f"{paths['tests']}/{scope}"
