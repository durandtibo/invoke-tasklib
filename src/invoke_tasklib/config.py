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


def get_config(c: Context) -> TasklibConfig:
    r"""Return the effective tasklib config, merging user overrides from
    ``invoke.yaml`` (under the ``tasklib`` key) on top of the defaults.

    Args:
        c: The invoke context.

    Returns:
        A dict with resolved ``package`` and ``paths`` sections.

    Raises:
        ValueError: If ``tasklib.package.name`` is not set.

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
            name=package["name"], python_version=str(package["python_version"])
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
        "groups": GroupsConfig(install=groups["install"], update=groups["update"]),
    }
