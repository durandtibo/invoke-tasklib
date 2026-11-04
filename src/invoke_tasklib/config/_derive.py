r"""Default values of the config that are derived from the project."""

from __future__ import annotations

import tomllib
from pathlib import Path

from invoke_tasklib.config._constants import (
    DEFAULT_PYTHON_VERSION,
    PYTHON_VERSION_PATTERN,
    REQUIRES_PYTHON_LOWER_BOUND,
    TEST_SCOPES,
)
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


def _python_version_file(root: Path) -> str | None:
    r"""Read the Python version of a ``.python-version`` file.

    Args:
        root: The project directory.

    Returns:
        The first line of the file that is not empty nor a comment, if
        it is a version like ``"3.12"`` or ``"3.12.1"``. ``None`` if
        the file does not exist or has any other content (an
        implementation name, a path, ...).

    Example usage:

    ```pycon
    >>> from pathlib import Path
    >>> from invoke_tasklib.config._derive import _python_version_file
    >>> _python_version_file(Path("no/such/dir")) is None
    True

    ```
    """
    path = root / ".python-version"
    if not path.is_file():
        return None
    for line in path.read_text().splitlines():
        version = line.strip()
        if version and not version.startswith("#"):
            return version if PYTHON_VERSION_PATTERN.fullmatch(version) else None
    return None


def _requires_python_lower_bound(root: Path) -> str | None:
    r"""Read the lower bound of ``requires-python``.

    The file read is the ``pyproject.toml`` of the project.

    Args:
        root: The project directory.

    Returns:
        The ``major.minor`` version of the first ``>=``, ``~=`` or
        ``==`` specifier of ``project.requires-python`` (``">=3.11"``
        gives ``"3.11"``). ``None`` if there is no such file, no such
        key or no such specifier, or if the file is not valid TOML.

    Example usage:

    ```pycon
    >>> from pathlib import Path
    >>> from invoke_tasklib.config._derive import (
    ...     _requires_python_lower_bound,
    ... )
    >>> _requires_python_lower_bound(Path("no/such/dir")) is None
    True

    ```
    """
    path = root / "pyproject.toml"
    if not path.is_file():
        return None
    try:
        requires = tomllib.loads(path.read_text()).get("project", {}).get("requires-python")
    except tomllib.TOMLDecodeError:
        return None
    match = REQUIRES_PYTHON_LOWER_BOUND.search(requires) if isinstance(requires, str) else None
    return match.group(1) if match else None


def _default_python_version(root: Path) -> str:
    r"""Return the default ``package.python_version`` of a project.

    The first available source wins: the ``.python-version`` file, the
    lower bound of ``requires-python`` in ``pyproject.toml``, and then
    ``DEFAULT_PYTHON_VERSION``.

    Args:
        root: The project directory.

    Returns:
        The version, like ``"3.12"``.

    Example usage:

    ```pycon
    >>> from pathlib import Path
    >>> from invoke_tasklib.config._derive import (
    ...     _default_python_version,
    ... )
    >>> _default_python_version(Path("no/such/dir"))
    '3.14'

    ```
    """
    return (
        _python_version_file(root) or _requires_python_lower_bound(root) or DEFAULT_PYTHON_VERSION
    )


def _derive_defaults(merged: dict[str, dict[str, object]]) -> None:
    r"""Fill the values of the config that are derived from others.

    Args:
        merged: The values of each section, defaults and user values
            merged. ``package.name`` must be a valid string. It is
            changed in place: ``package.python_version``,
            ``package.import_name``, ``paths.src`` and the paths of the
            test scopes that are not set get their default.

    Raises:
        ValueError: If ``package.import_name`` is not a Python module
            name (and ``paths.src`` has to be derived from it).

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._derive import _derive_defaults
    >>> package = {"name": "my-pkg", "import_name": None}
    >>> package["python_version"] = "3.12"
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
    if package["python_version"] is None:
        package["python_version"] = _default_python_version(Path())
    if package["import_name"] is None:
        package["import_name"] = str(package["name"]).replace("-", "_")
    if paths["src"] is None:
        paths["src"] = _default_src(_validate_import_name(package["import_name"]))
    for key, scope in TEST_SCOPES.items():
        if paths[key] is None:
            paths[key] = f"{paths['tests']}/{scope}"
