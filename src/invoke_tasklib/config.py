r"""Config resolution for invoke-tasklib tasks.

Consuming projects set project-specific values under a ``tasklib`` key
in their ``invoke.yaml``, e.g.::

    tasklib:
      package:
        name: coola
      paths:
        docs_config: docs/mkdocs.yml

Only ``package.name`` (the distribution name) is required; everything
else has a default derived from it. ``package.import_name`` defaults to
the name with ``-`` replaced by ``_``.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.exceptions import Exit

if TYPE_CHECKING:
    from collections.abc import Iterable

    from invoke.context import Context


_SECTIONS = ("package", "paths", "groups", "test")


@dataclass(frozen=True)
class PackageConfig:
    r"""Resolved ``package`` config section."""

    name: str
    import_name: str
    python_version: str


@dataclass(frozen=True)
class PathsConfig:
    r"""Resolved ``paths`` config section."""

    src: str
    tests: str
    unit_tests: str
    integration_tests: str
    functional_tests: str
    benchmarks: str
    docs_config: str


@dataclass(frozen=True)
class GroupsConfig:
    r"""Resolved ``groups`` config section."""

    install: str
    update: str


@dataclass(frozen=True)
class TestConfig:
    r"""Resolved ``test`` config section."""

    unit_timeout: int
    integration_timeout: int
    functional_timeout: int
    xdoctest: bool
    cov_fail_under: int | None
    cov_reports: tuple[str, ...]


@dataclass(frozen=True)
class TasklibConfig:
    r"""Resolved tasklib config."""

    package: PackageConfig
    paths: PathsConfig
    groups: GroupsConfig
    test: TestConfig


EXCLUDED_DIRS: frozenset[str] = frozenset({".venv", ".pytest_cache", ".git", "node_modules"})
r"""Directories that the tasks never walk into (not owned by the
project)."""

PYTHON_VERSION_PATTERN = re.compile(r"\d+\.\d+(\.\d+)?")
r"""Pattern of a valid ``package.python_version`` (``3.10`` or
``3.10.4``)."""

DEFAULT_PACKAGE: dict[str, str | None] = {
    "name": None,
    "import_name": None,
    "python_version": "3.14",
}

DEFAULT_PATHS: dict[str, str | None] = {
    "src": None,
    "tests": "tests",
    "unit_tests": None,
    "integration_tests": None,
    "functional_tests": None,
    "benchmarks": None,
    "docs_config": "docs/mkdocs.yml",
}

DEFAULT_GROUPS: dict[str, str] = {
    "install": "dev",
    "update": "dev,docs",
}

COV_REPORTS: frozenset[str] = frozenset(
    {"html", "xml", "json", "lcov", "annotate", "term", "term-missing"}
)
r"""The valid values of ``test.cov_reports`` (the formats of ``--cov-
report`` of pytest-cov)."""

DEFAULT_TEST: dict[str, int | bool | str | None] = {
    "unit_timeout": 10,
    "integration_timeout": 60,
    "functional_timeout": 60,
    "xdoctest": True,
    "cov_fail_under": None,
    "cov_reports": "html,xml,term",
}


def default_config() -> dict[str, dict[str, object]]:
    r"""Return the defaults of the ``tasklib`` config section.

    The defaults are registered with Invoke (see ``make_ns``) so that
    the keys can also be set with the ``INVOKE_TASKLIB_<SECTION>_<KEY>``
    environment variables, for example ``INVOKE_TASKLIB_PATHS_SRC``.
    Invoke only reads an environment variable for a key that exists in
    the defaults.

    Returns:
        A new dict with the ``package``, ``paths``, ``groups`` and
        ``test`` sections, each a copy of its ``DEFAULT_*`` dict.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import default_config
    >>> sorted(default_config())
    ['groups', 'package', 'paths', 'test']
    >>> default_config()["groups"]
    {'install': 'dev', 'update': 'dev,docs'}

    ```
    """
    return {
        "package": dict(DEFAULT_PACKAGE),
        "paths": dict(DEFAULT_PATHS),
        "groups": dict(DEFAULT_GROUPS),
        "test": dict(DEFAULT_TEST),
    }


_TEST_SCOPES: dict[str, str] = {
    "unit_tests": "unit",
    "integration_tests": "integration",
    "functional_tests": "functional",
    "benchmarks": "benchmarks",
}
r"""Default sub-directory of ``paths.tests`` of each test path."""


def _validate_python_version(value: object) -> str:
    r"""Validate the ``package.python_version`` config value.

    YAML reads an unquoted ``3.10`` as the float ``3.1``, which would
    silently select the wrong Python version, so only quoted strings
    such as ``"3.10"`` or ``"3.10.4"`` are accepted.

    Args:
        value: The raw config value.

    Returns:
        The validated version string.

    Raises:
        ValueError: If the value is not a string like ``"3.10"`` or
            ``"3.10.4"``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _validate_python_version
    >>> _validate_python_version("3.10")
    '3.10'

    ```
    """
    if not isinstance(value, str) or not PYTHON_VERSION_PATTERN.fullmatch(value):
        msg = (
            f'\'tasklib.package.python_version\' must be a string like "3.10" or "3.10.4", '
            f"got {value!r}. Quote the value in invoke.yaml: YAML reads an unquoted 3.10 "
            "as the number 3.1."
        )
        raise ValueError(msg)
    return value


def _as_mapping(name: str, value: object) -> Mapping[str, object]:
    r"""Check that a config section is a mapping.

    Without this check, a string given instead of a section would be
    read character by character by the key validation.

    Args:
        name: The dotted name of the section (``tasklib`` or
            ``tasklib.paths``), used in the error message.
        value: The raw value of the section.

    Returns:
        The section, unchanged.

    Raises:
        ValueError: If ``value`` is not a mapping.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _as_mapping
    >>> _as_mapping("tasklib.paths", {"src": "x"})
    {'src': 'x'}
    >>> _as_mapping("tasklib.paths", "foo")
    Traceback (most recent call last):
        ...
    ValueError: 'tasklib.paths' must be a mapping, got 'foo'

    ```
    """
    if isinstance(value, Mapping):
        return value
    msg = f"'{name}' must be a mapping, got {value!r}"
    raise ValueError(msg)


def _check_keys(section: str, user: Mapping[str, object], valid: Iterable[str]) -> None:
    r"""Check that a user config section only has known keys.

    Args:
        section: The name of the section (``package``, ``paths``,
            ``groups`` or ``test``), used in the error message. An
            empty string stands for the ``tasklib`` section itself.
        user: The user values of the section.
        valid: The valid keys of the section.

    Raises:
        ValueError: If ``user`` has keys that are not in ``valid``. The
            message lists the unknown keys, with the closest valid key
            when there is one, and the valid keys.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _check_keys
    >>> _check_keys("paths", {"src": "x"}, ["src", "tests"])
    >>> _check_keys("paths", {"sr": "x"}, ["src", "tests"])
    Traceback (most recent call last):
        ...
    ValueError: Unknown key 'sr' (did you mean 'src'?) in
    'tasklib.paths'. Valid keys: src, tests

    ```
    """
    valid_keys = sorted(valid)
    unknown = sorted(set(user) - set(valid_keys))
    if not unknown:
        return
    details = []
    for key in unknown:
        close = difflib.get_close_matches(key, valid_keys, n=1)
        hint = f" (did you mean '{close[0]}'?)" if close else ""
        details.append(f"'{key}'{hint}")
    noun = "key" if len(unknown) == 1 else "keys"
    location = f"tasklib.{section}" if section else "tasklib"
    msg = (
        f"Unknown {noun} {', '.join(details)} in '{location}'. Valid keys: {', '.join(valid_keys)}"
    )
    raise ValueError(msg)


def _normalize_groups(key: str, value: object) -> str:
    r"""Normalize a ``groups`` config value to a comma-separated string.

    Args:
        key: The name of the config key, used in the error message.
        value: The raw config value: a comma-separated string or a list
            of group names.

    Returns:
        The groups as a comma-separated string.

    Raises:
        ValueError: If the value is neither a string nor a list of
            strings.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _normalize_groups
    >>> _normalize_groups("install", ["dev", "docs"])
    'dev,docs'
    >>> _normalize_groups("install", "dev,docs")
    'dev,docs'

    ```
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and all(isinstance(g, str) for g in value):
        return ",".join(value)
    msg = (
        f"'tasklib.groups.{key}' must be a comma-separated string or a list of strings, "
        f"got {value!r}"
    )
    raise ValueError(msg)


def _validate_import_name(value: object) -> str:
    r"""Validate the ``package.import_name`` config value.

    Args:
        value: The raw config value.

    Returns:
        The validated import name.

    Raises:
        ValueError: If the value is not a string of Python identifiers
            separated by dots, e.g. ``"my_package"``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _validate_import_name
    >>> _validate_import_name("my_package")
    'my_package'

    ```
    """
    if not isinstance(value, str) or not all(part.isidentifier() for part in value.split(".")):
        msg = (
            "'tasklib.package.import_name' must be a Python module name such as "
            f'"my_package", got {value!r}'
        )
        raise ValueError(msg)
    return value


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
    >>> from invoke_tasklib.config import _default_src
    >>> _default_src("no_such_package")
    'src/no_such_package'

    ```
    """
    src_layout = f"src/{import_name}"
    if not Path(src_layout).is_dir() and Path(import_name).is_dir():
        return import_name
    return src_layout


def _validate_int(key: str, value: object, *, minimum: int, maximum: int | None = None) -> int:
    r"""Validate an integer value of the ``test`` config section.

    Args:
        key: The name of the config key, used in the error message.
        value: The raw config value.
        minimum: The smallest valid value.
        maximum: The largest valid value, or ``None`` for no limit.

    Returns:
        The validated integer.

    Raises:
        ValueError: If the value is not an integer (a boolean is not
            accepted), is smaller than ``minimum`` or is larger than
            ``maximum``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _validate_int
    >>> _validate_int("unit_timeout", 10, minimum=1)
    10

    ```
    """
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        bounds = f">= {minimum}" if maximum is None else f"between {minimum} and {maximum}"
        msg = f"'tasklib.test.{key}' must be an integer {bounds}, got {value!r}"
        raise ValueError(msg)
    return value


def _validate_str(section: str, key: str, value: object) -> str:
    r"""Validate a string value of the ``package`` or ``paths`` section.

    Args:
        section: The name of the config section, used in the error
            message.
        key: The name of the config key, used in the error message.
        value: The raw config value.

    Returns:
        The validated string.

    Raises:
        ValueError: If the value is not a string, or is empty.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _validate_str
    >>> _validate_str("paths", "src", "src/mypkg")
    'src/mypkg'

    ```
    """
    if not isinstance(value, str) or not value:
        msg = f"'tasklib.{section}.{key}' must be a non-empty string, got {value!r}"
        raise ValueError(msg)
    return value


def _int_from_text(value: object) -> object:
    r"""Convert a string of digits to an integer.

    Invoke reads an environment variable as a string, unless the default
    of the key is a number or a boolean. The ``cov_fail_under`` key has
    no default, so ``INVOKE_TASKLIB_TEST_COV_FAIL_UNDER=90`` is the
    string ``"90"``.

    Args:
        value: The raw config value.

    Returns:
        The integer if ``value`` is a string of ASCII digits, ``value``
        unchanged otherwise.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _int_from_text
    >>> _int_from_text("90")
    90
    >>> _int_from_text(90)
    90

    ```
    """
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return value


def _validate_cov_reports(value: object) -> tuple[str, ...]:
    r"""Validate the ``test.cov_reports`` config value.

    Args:
        value: The raw config value: a comma-separated string or a list
            of report formats.

    Returns:
        The report formats, without duplicates, in the order given.

    Raises:
        ValueError: If the value is neither a string nor a list of
            strings, or if a format is not one of ``COV_REPORTS``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _validate_cov_reports
    >>> _validate_cov_reports("html, term")
    ('html', 'term')
    >>> _validate_cov_reports(["xml"])
    ('xml',)

    ```
    """
    if isinstance(value, str):
        names = [name.strip() for name in value.split(",")]
    elif isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        names = [name.strip() for name in value]
    else:
        msg = (
            "'tasklib.test.cov_reports' must be a comma-separated string or a list of "
            f"strings, got {value!r}"
        )
        raise ValueError(msg)
    names = list(dict.fromkeys(name for name in names if name))
    unknown = [name for name in names if name not in COV_REPORTS]
    if unknown:
        msg = (
            f"Unknown coverage report {unknown} in 'tasklib.test.cov_reports'. "
            f"Valid reports: {', '.join(sorted(COV_REPORTS))}"
        )
        raise ValueError(msg)
    return tuple(names)


def _validate_bool(key: str, value: object) -> bool:
    r"""Validate a boolean value of the ``test`` config section.

    Args:
        key: The name of the config key, used in the error message.
        value: The raw config value.

    Returns:
        The validated boolean.

    Raises:
        ValueError: If the value is not a boolean.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _validate_bool
    >>> _validate_bool("xdoctest", False)
    False

    ```
    """
    if value is not True and value is not False:
        msg = f"'tasklib.test.{key}' must be a boolean (true or false), got {value!r}"
        raise ValueError(msg)
    return value


def get_config(c: Context) -> TasklibConfig:
    r"""Return the effective tasklib config, merging user overrides from
    ``invoke.yaml`` (under the ``tasklib`` key) on top of the defaults.

    Args:
        c: The invoke context.

    Returns:
        A frozen dataclass with the resolved ``package``, ``paths``,
        ``groups`` and ``test`` sections, each a frozen dataclass too,
        e.g. ``cfg.paths.src``.

    Raises:
        ValueError: If ``tasklib`` or one of its ``package``, ``paths``,
            ``groups`` and ``test`` sections is not a mapping, or if
            ``tasklib`` has a key that is not one of these sections, or
            if ``tasklib.package.name`` is not set or is not a string,
            or if a ``tasklib.paths`` value is not a non-empty string,
            or if ``tasklib.package.python_version`` is not a string
            such as ``"3.10"`` (an unquoted ``3.10`` is read by YAML as
            the float ``3.1``), or if ``tasklib.package.import_name`` is
            not a Python module name, or if a ``tasklib.groups`` value
            is neither a string nor a list of strings, or if the
            ``package``, ``paths``, ``groups`` or ``test`` section has
            an unknown key (for example a typo such as ``unit_test`` for
            ``unit_tests``), or if a ``tasklib.test`` value is invalid
            (a timeout and ``cov_fail_under`` must be integers, with a
            timeout > 0 and ``cov_fail_under`` between 0 and 100,
            ``cov_reports`` must be report formats, and ``xdoctest``
            must be a boolean).

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.config import get_config
    >>> overrides = {"tasklib": {"package": {"name": "mypkg"}}}
    >>> c = Context(config=Config(overrides=overrides))
    >>> cfg = get_config(c)
    >>> cfg.package.import_name
    'mypkg'
    >>> cfg.paths.src
    'src/mypkg'
    >>> cfg.groups
    GroupsConfig(install='dev', update='dev,docs')
    >>> cfg.test.unit_timeout
    10

    ```
    """
    user = _as_mapping("tasklib", c.config.get("tasklib", {}))
    _check_keys("", user, _SECTIONS)
    sections = {name: _as_mapping(f"tasklib.{name}", user.get(name, {})) for name in _SECTIONS}
    _check_keys("package", sections["package"], DEFAULT_PACKAGE)
    _check_keys("paths", sections["paths"], DEFAULT_PATHS)
    _check_keys("groups", sections["groups"], DEFAULT_GROUPS)
    _check_keys("test", sections["test"], DEFAULT_TEST)
    package = {**DEFAULT_PACKAGE, **sections["package"]}
    paths = {**DEFAULT_PATHS, **sections["paths"]}
    groups = {**DEFAULT_GROUPS, **sections["groups"]}
    test = {**DEFAULT_TEST, **sections["test"]}

    if not package["name"]:
        msg = "'tasklib.package.name' must be set in invoke.yaml"
        raise ValueError(msg)
    name = _validate_str("package", "name", package["name"])

    import_name = _validate_import_name(
        package["import_name"] if package["import_name"] is not None else name.replace("-", "_")
    )
    if paths["src"] is None:
        paths["src"] = _default_src(import_name)
    for key, scope in _TEST_SCOPES.items():
        if paths[key] is None:
            paths[key] = f"{paths['tests']}/{scope}"

    return TasklibConfig(
        package=PackageConfig(
            name=name,
            import_name=import_name,
            python_version=_validate_python_version(package["python_version"]),
        ),
        paths=PathsConfig(
            src=_validate_str("paths", "src", paths["src"]),
            tests=_validate_str("paths", "tests", paths["tests"]),
            unit_tests=_validate_str("paths", "unit_tests", paths["unit_tests"]),
            integration_tests=_validate_str(
                "paths", "integration_tests", paths["integration_tests"]
            ),
            functional_tests=_validate_str("paths", "functional_tests", paths["functional_tests"]),
            benchmarks=_validate_str("paths", "benchmarks", paths["benchmarks"]),
            docs_config=_validate_str("paths", "docs_config", paths["docs_config"]),
        ),
        groups=GroupsConfig(
            install=_normalize_groups("install", groups["install"]),
            update=_normalize_groups("update", groups["update"]),
        ),
        test=TestConfig(
            unit_timeout=_validate_int("unit_timeout", test["unit_timeout"], minimum=1),
            integration_timeout=_validate_int(
                "integration_timeout", test["integration_timeout"], minimum=1
            ),
            functional_timeout=_validate_int(
                "functional_timeout", test["functional_timeout"], minimum=1
            ),
            xdoctest=_validate_bool("xdoctest", test["xdoctest"]),
            cov_fail_under=(
                None
                if test["cov_fail_under"] is None
                else _validate_int(
                    "cov_fail_under",
                    _int_from_text(test["cov_fail_under"]),
                    minimum=0,
                    maximum=100,
                )
            ),
            cov_reports=_validate_cov_reports(test["cov_reports"]),
        ),
    )


def load_config(c: Context) -> TasklibConfig:
    r"""Return the effective tasklib config, exiting cleanly on an
    invalid config.

    The tasks use this function instead of ``get_config`` so that an
    invalid config is reported as a one-line message and the exit code
    2 rather than as a Python traceback. ``get_config`` is the function
    to use programmatically, because it raises a ``ValueError``.

    Args:
        c: The invoke context.

    Returns:
        The resolved config, see ``get_config``.

    Raises:
        Exit: If ``get_config`` raises a ``ValueError``. The message is
            the one of the ``ValueError``.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.config import load_config
    >>> overrides = {"tasklib": {"package": {"name": "mypkg"}}}
    >>> c = Context(config=Config(overrides=overrides))
    >>> load_config(c).package.name
    'mypkg'

    ```
    """
    try:
        return get_config(c)
    except ValueError as exc:
        raise Exit(str(exc), code=2) from exc
