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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from invoke.context import Context


DEFAULT_PACKAGE = {
    "name": None,
    "python_version": "3.14",
}

DEFAULT_PATHS = {
    "src": None,
    "tests": "tests",
    "unit_tests": None,
    "integration_tests": None,
    "benchmarks": None,
    "docs_config": "docs/mkdocs.yml",
}


def get_config(c: Context) -> dict:
    r"""Return the effective tasklib config, merging user overrides from
    ``invoke.yaml`` (under the ``tasklib`` key) on top of the defaults.

    Args:
        c: The invoke context.

    Returns:
        A dict with resolved ``package`` and ``paths`` sections.

    Raises:
        ValueError: If ``tasklib.package.name`` is not set.
    """
    user = dict(c.config.get("tasklib", {}))
    package = {**DEFAULT_PACKAGE, **user.get("package", {})}
    paths = {**DEFAULT_PATHS, **user.get("paths", {})}

    if not package["name"]:
        msg = "'tasklib.package.name' must be set in invoke.yaml"
        raise ValueError(msg)

    if not paths["src"]:
        paths["src"] = f"src/{package['name']}"
    if not paths["unit_tests"]:
        paths["unit_tests"] = f"{paths['tests']}/unit"
    if not paths["integration_tests"]:
        paths["integration_tests"] = f"{paths['tests']}/integration"
    if not paths["benchmarks"]:
        paths["benchmarks"] = f"{paths['tests']}/benchmarks"

    return {"package": package, "paths": paths}
