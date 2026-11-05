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

from invoke_tasklib.config._resolve import get_config, load_config
from invoke_tasklib.config._schema import (
    SCHEMA,
    CheckConfig,
    FixConfig,
    GroupsConfig,
    Option,
    PackageConfig,
    PathsConfig,
    TasklibConfig,
    TestConfig,
    TypesConfig,
    default_config,
    json_schema,
)

__all__ = [
    "SCHEMA",
    "CheckConfig",
    "FixConfig",
    "GroupsConfig",
    "Option",
    "PackageConfig",
    "PathsConfig",
    "TasklibConfig",
    "TestConfig",
    "TypesConfig",
    "default_config",
    "get_config",
    "json_schema",
    "load_config",
]
