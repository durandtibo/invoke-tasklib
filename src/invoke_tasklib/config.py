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

import re
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
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


class TasklibConfig(TypedDict):
    r"""Resolved tasklib config."""

    package: PackageConfig
    paths: PathsConfig
    groups: GroupsConfig


EXCLUDED_DIRS: frozenset[str] = frozenset({".venv", ".pytest_cache", ".git", "node_modules"})
r"""Directories that the tasks never walk into (not owned by the project)."""

PYTHON_VERSION_PATTERN = re.compile(r"\d+\.\d+(\.\d+)?")
r"""Pattern of a valid ``package.python_version`` (``3.10`` or ``3.10.4``)."""

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


def get_config(c: Context) -> TasklibConfig:
    r"""Return the effective tasklib config, merging user overrides from
    ``invoke.yaml`` (under the ``tasklib`` key) on top of the defaults.

    Args:
        c: The invoke context.

    Returns:
        A dict with resolved ``package`` and ``paths`` sections.

    Raises:
        ValueError: If ``tasklib.package.name`` is not set, or if
            ``tasklib.package.python_version`` is not a string such as
            ``"3.10"`` (an unquoted ``3.10`` is read by YAML as the
            float ``3.1``), or if a ``tasklib.groups`` value is neither
            a string nor a list of strings.

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

    ```
    """
    user = dict(c.config.get("tasklib", {}))
    package = {**DEFAULT_PACKAGE, **user.get("package", {})}
    paths = {**DEFAULT_PATHS, **user.get("paths", {})}
    groups = {**DEFAULT_GROUPS, **user.get("groups", {})}

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
    }
