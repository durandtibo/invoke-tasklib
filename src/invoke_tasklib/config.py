r"""Config resolution for invoke-tasklib tasks.

Consuming projects set project-specific values under a ``tasklib`` key in
their ``invoke.yaml``, e.g.::

    tasklib:
      package:
        name: coola
      paths:
        docs_config: docs/mkdocs.yml

Only ``package.name`` is required; everything else has a default derived
from it.
"""

from __future__ import annotations

import difflib
import re
from typing import TYPE_CHECKING, TypedDict

from invoke.exceptions import Exit

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from invoke.context import Context


class PackageConfig(TypedDict):
    r"""Resolved ``package`` config section."""

    name: str
    python_version: str


class PathsConfig(TypedDict):
    r"""Resolved ``paths`` config section."""

    src: str
    tests: str
    unit_tests: str
    integration_tests: str
    functional_tests: str
    benchmarks: str
    docs_config: str


class GroupsConfig(TypedDict):
    r"""Resolved ``groups`` config section."""

    install: str
    update: str


class TestConfig(TypedDict):
    r"""Resolved ``test`` config section."""

    unit_timeout: int
    integration_timeout: int
    functional_timeout: int
    xdoctest: bool
    cov_fail_under: int | None


class TasklibConfig(TypedDict):
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

DEFAULT_TEST: dict[str, int | bool | None] = {
    "unit_timeout": 10,
    "integration_timeout": 60,
    "functional_timeout": 60,
    "xdoctest": True,
    "cov_fail_under": None,
}


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


def _check_keys(section: str, user: Mapping[str, object], valid: Iterable[str]) -> None:
    r"""Check that a user config section only has known keys.

    Args:
        section: The name of the section (``package``, ``paths`` or
            ``groups``), used in the error message.
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
    ValueError: Unknown key 'sr' (did you mean 'src'?) in 'tasklib.paths'. Valid keys: src, tests

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
    msg = (
        f"Unknown {noun} {', '.join(details)} in 'tasklib.{section}'. "
        f"Valid keys: {', '.join(valid_keys)}"
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


def _validate_int(key: str, value: object, *, minimum: int) -> int:
    r"""Validate an integer value of the ``test`` config section.

    Args:
        key: The name of the config key, used in the error message.
        value: The raw config value.
        minimum: The smallest valid value.

    Returns:
        The validated integer.

    Raises:
        ValueError: If the value is not an integer (a boolean is not
            accepted) or is smaller than ``minimum``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _validate_int
    >>> _validate_int("unit_timeout", 10, minimum=1)
    10

    ```
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        msg = f"'tasklib.test.{key}' must be an integer >= {minimum}, got {value!r}"
        raise ValueError(msg)
    return value


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
        A dict with the resolved ``package``, ``paths``, ``groups`` and
        ``test`` sections.

    Raises:
        ValueError: If ``tasklib.package.name`` is not set, or if
            ``tasklib.package.python_version`` is not a string such as
            ``"3.10"`` (an unquoted ``3.10`` is read by YAML as the
            float ``3.1``), or if a ``tasklib.groups`` value is neither
            a string nor a list of strings, or if the ``package``,
            ``paths``, ``groups`` or ``test`` section has an unknown key (for
            example a typo such as ``unit_test`` for ``unit_tests``), or
            if a ``tasklib.test`` value is invalid (a timeout and
            ``cov_fail_under`` must be integers, with a timeout > 0 and
            ``cov_fail_under`` >= 0, and ``xdoctest`` must be a
            boolean).

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.config import get_config
    >>> c = Context(config=Config(overrides={"tasklib": {"package": {"name": "mypkg"}}}))
    >>> cfg = get_config(c)
    >>> cfg["package"]
    {'name': 'mypkg', 'python_version': '3.14'}
    >>> cfg["paths"]["src"]
    'src/mypkg'
    >>> cfg["groups"]
    {'install': 'dev', 'update': 'dev,docs'}
    >>> cfg["test"]["unit_timeout"]
    10

    ```
    """
    user = dict(c.config.get("tasklib", {}))
    _check_keys("package", user.get("package", {}), DEFAULT_PACKAGE)
    _check_keys("paths", user.get("paths", {}), DEFAULT_PATHS)
    _check_keys("groups", user.get("groups", {}), DEFAULT_GROUPS)
    _check_keys("test", user.get("test", {}), DEFAULT_TEST)
    package = {**DEFAULT_PACKAGE, **user.get("package", {})}
    paths = {**DEFAULT_PATHS, **user.get("paths", {})}
    groups = {**DEFAULT_GROUPS, **user.get("groups", {})}
    test = {**DEFAULT_TEST, **user.get("test", {})}

    if not package["name"]:
        msg = "'tasklib.package.name' must be set in invoke.yaml"
        raise ValueError(msg)

    if not paths["src"]:
        paths["src"] = f"src/{package['name']}"
    if not paths["unit_tests"]:
        paths["unit_tests"] = f"{paths['tests']}/unit"
    if not paths["integration_tests"]:
        paths["integration_tests"] = f"{paths['tests']}/integration"
    if not paths["functional_tests"]:
        paths["functional_tests"] = f"{paths['tests']}/functional"
    if not paths["benchmarks"]:
        paths["benchmarks"] = f"{paths['tests']}/benchmarks"

    return {
        "package": PackageConfig(
            name=package["name"],
            python_version=_validate_python_version(package["python_version"]),
        ),
        "paths": PathsConfig(
            src=str(paths["src"]),
            tests=str(paths["tests"]),
            unit_tests=str(paths["unit_tests"]),
            integration_tests=str(paths["integration_tests"]),
            functional_tests=str(paths["functional_tests"]),
            benchmarks=str(paths["benchmarks"]),
            docs_config=str(paths["docs_config"]),
        ),
        "groups": GroupsConfig(
            install=_normalize_groups("install", groups["install"]),
            update=_normalize_groups("update", groups["update"]),
        ),
        "test": TestConfig(
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
                else _validate_int("cov_fail_under", test["cov_fail_under"], minimum=0)
            ),
        ),
    }


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
    >>> c = Context(config=Config(overrides={"tasklib": {"package": {"name": "mypkg"}}}))
    >>> load_config(c)["package"]["name"]
    'mypkg'

    ```
    """
    try:
        return get_config(c)
    except ValueError as exc:
        raise Exit(str(exc), code=2) from exc
