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

from invoke_tasklib.config._constants import (
    CHECK_STEPS,
    COV_REPORTS,
    EXCLUDED_DIRS,
    FIX_STEPS,
    PYTHON_VERSION_PATTERN,
)
from invoke_tasklib.config._resolve import PROJECT_PREFIX_ATTRIBUTE, get_config, load_config
from invoke_tasklib.config._schema import (
    DEFAULT_CHECK,
    DEFAULT_FIX,
    DEFAULT_GROUPS,
    DEFAULT_PACKAGE,
    DEFAULT_PATHS,
    DEFAULT_TEST,
    DEFAULT_TYPES,
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
    Unset,
    default_config,
    json_schema,
    main,
)

__all__ = [
    "CHECK_STEPS",
    "COV_REPORTS",
    "DEFAULT_CHECK",
    "DEFAULT_FIX",
    "DEFAULT_GROUPS",
    "DEFAULT_PACKAGE",
    "DEFAULT_PATHS",
    "DEFAULT_TEST",
    "DEFAULT_TYPES",
    "EXCLUDED_DIRS",
    "FIX_STEPS",
    "PROJECT_PREFIX_ATTRIBUTE",
    "PYTHON_VERSION_PATTERN",
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
    "Unset",
    "default_config",
    "get_config",
    "json_schema",
    "load_config",
    "main",
]
