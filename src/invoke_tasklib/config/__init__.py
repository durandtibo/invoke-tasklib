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

from typing import TYPE_CHECKING

from invoke.exceptions import Exit

from invoke_tasklib.config._constants import (
    CHECK_STEPS,
    COV_REPORTS,
    DEFAULT_PYTHON_VERSION,
    EXCLUDED_DIRS,
    FIX_STEPS,
    PYTHON_VERSION_PATTERN,
)
from invoke_tasklib.config._derive import _derive_defaults
from invoke_tasklib.config._schema import (
    _SECTION_CLASSES,
    DEFAULT_CHECK,
    DEFAULT_FIX,
    DEFAULT_GROUPS,
    DEFAULT_PACKAGE,
    DEFAULT_PATHS,
    DEFAULT_TEST,
    SCHEMA,
    CheckConfig,
    FixConfig,
    GroupsConfig,
    Option,
    PackageConfig,
    PathsConfig,
    TasklibConfig,
    TestConfig,
    _defaults,
    default_config,
    json_schema,
    main,
)
from invoke_tasklib.config._validate import _as_mapping, _check_keys, _validate_str

__all__ = [
    "CHECK_STEPS",
    "COV_REPORTS",
    "DEFAULT_CHECK",
    "DEFAULT_FIX",
    "DEFAULT_GROUPS",
    "DEFAULT_PACKAGE",
    "DEFAULT_PATHS",
    "DEFAULT_PYTHON_VERSION",
    "DEFAULT_TEST",
    "EXCLUDED_DIRS",
    "FIX_STEPS",
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
    "default_config",
    "get_config",
    "json_schema",
    "load_config",
    "main",
]

if TYPE_CHECKING:
    from invoke.context import Context


def get_config(c: Context) -> TasklibConfig:
    r"""Return the effective tasklib config, merging user overrides from
    ``invoke.yaml`` (under the ``tasklib`` key) on top of the defaults.

    Args:
        c: The invoke context.

    Returns:
        A frozen dataclass with the resolved ``package``, ``paths``,
        ``groups``, ``test``, ``check`` and ``fix`` sections, each a
        frozen dataclass too, e.g. ``cfg.paths.src``.

    Raises:
        ValueError: If ``tasklib`` or one of its sections (``package``,
            ``paths``, ``groups``, ``test``, ``check`` and ``fix``) is
            not a mapping, or if ``tasklib`` or a section has an
            unknown key
            (for example a typo such as ``unit_test`` for
            ``unit_tests``), or if ``tasklib.package.name`` is not set
            or is not a string, or if a ``tasklib.paths`` value is not
            a non-empty string, or if ``tasklib.package.python_version``
            is not a string such as ``"3.10"`` (an unquoted ``3.10`` is
            read by YAML as the float ``3.1``), or if
            ``tasklib.package.import_name`` is not a Python module
            name, or if a ``tasklib.groups`` value is neither a string
            nor a list of strings, or if a ``tasklib.test`` value is
            invalid (a timeout and ``cov_fail_under`` must be integers,
            with a timeout > 0 and ``cov_fail_under`` between 0 and
            100, ``cov_reports`` must be report formats, and
            ``xdoctest`` must be a boolean), or if
            ``tasklib.check.tasks`` or ``tasklib.fix.tasks`` is empty
            or has an unknown step.

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
    GroupsConfig(install=('dev',), update=('dev', 'docs'))
    >>> cfg.test.unit_timeout
    10
    >>> cfg.check.tasks[0]
    'format-python'

    ```
    """
    user = _as_mapping("tasklib", c.config.get("tasklib", {}))
    _check_keys("", user, SCHEMA)
    merged: dict[str, dict[str, object]] = {}
    for section, options in SCHEMA.items():
        given = _as_mapping(f"tasklib.{section}", user.get(section, {}))
        _check_keys(section, given, options)
        merged[section] = {**_defaults(section), **given}
    package = merged["package"]

    if not package["name"]:
        msg = "'tasklib.package.name' must be set in invoke.yaml"
        raise ValueError(msg)
    package["name"] = _validate_str("package", "name", package["name"])
    _derive_defaults(merged)

    resolved = {
        section: _SECTION_CLASSES[section](
            **{key: option.validate(merged[section][key]) for key, option in options.items()}
        )
        for section, options in SCHEMA.items()
    }
    return TasklibConfig(**resolved)


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
