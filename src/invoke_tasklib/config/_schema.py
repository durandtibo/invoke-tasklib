r"""Schema of the config: the options, their defaults and sections."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, get_type_hints

from invoke_tasklib.config._constants import (
    COV_REPORTS,
    PYTHON_VERSION_PATTERN,
    TYPE_CHECKERS,
)
from invoke_tasklib.config._validate import (
    _normalize_groups,
    _validate_bool,
    _validate_checker,
    _validate_cov_fail_under,
    _validate_cov_reports,
    _validate_import_name,
    _validate_int,
    _validate_python_version,
    _validate_steps,
    _validate_str,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


@dataclass(frozen=True)
class PackageConfig:
    r"""Resolved ``package`` config section."""

    name: str
    import_name: str
    python_version: str | None


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

    install: tuple[str, ...]
    update: tuple[str, ...]


@dataclass(frozen=True)
class TestConfig:
    r"""Resolved ``test`` config section."""

    unit_timeout: int
    integration_timeout: int
    functional_timeout: int
    xdoctest: bool
    timeout: bool
    cov_fail_under: int | None
    cov_reports: tuple[str, ...]


@dataclass(frozen=True)
class TypesConfig:
    r"""Resolved ``types`` config section."""

    checker: str


@dataclass(frozen=True)
class CheckConfig:
    r"""Resolved ``check`` config section."""

    tasks: tuple[str, ...] | None
    cov: bool


@dataclass(frozen=True)
class FixConfig:
    r"""Resolved ``fix`` config section."""

    tasks: tuple[str, ...] | None


@dataclass(frozen=True)
class TasklibConfig:
    r"""Resolved tasklib config."""

    package: PackageConfig
    paths: PathsConfig
    groups: GroupsConfig
    test: TestConfig
    types: TypesConfig
    check: CheckConfig
    fix: FixConfig


@dataclass(frozen=True)
class Option:
    r"""Declaration of one key of the ``tasklib`` config.

    It is the single place that declares the key.

    Attributes:
        default: The default value. ``None`` means that the default is
            derived from other values (see ``get_config``), that the
            key is required (``package.name``), that the key is not set
            (``package.python_version``, ``test.cov_fail_under``), or
            that the composite task chooses the steps (``check.tasks``,
            ``fix.tasks``). A default is a tuple for a list.
        validate: Check a raw value and return the resolved one. It
            raises ``ValueError`` with a message that names the key.
        json_schema: The JSON schema of the key, without ``default``.
        doc: One-line description, used by the JSON schema.
    """

    default: object
    validate: Callable[[str, object], object]
    json_schema: Mapping[str, object]
    doc: str = ""


_STRING = {"type": "string", "minLength": 1}


_NAMES = {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}


def _timeout(default: int, doc: str) -> Option:
    r"""Declare a per-test timeout key of the ``test`` section.

    Args:
        default: The timeout in seconds.
        doc: The description of the key.

    Returns:
        The option.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._schema import _timeout
    >>> _timeout(10, "Timeout.").default
    10

    ```
    """
    return Option(
        default,
        partial(_validate_int, minimum=1),
        {"type": "integer", "minimum": 1},
        doc,
    )


def _path(default: str | None, doc: str) -> Option:
    r"""Declare a key of the ``paths`` section.

    Args:
        default: The default path, or ``None`` if it is derived.
        doc: The description of the key.

    Returns:
        The option.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._schema import _path
    >>> _path("tests", "Tests.").default
    'tests'

    ```
    """
    return Option(default, _validate_str, _STRING, doc)


_COV_REPORT_PATTERN = f"^({'|'.join(sorted(COV_REPORTS))})(:.+)?$"


SCHEMA: dict[str, dict[str, Option]] = {
    "package": {
        "name": Option(
            None,
            _validate_str,
            _STRING,
            "Distribution name, as on PyPI (required).",
        ),
        "import_name": Option(
            None,
            _validate_import_name,
            _STRING,
            "Name used to import the package (default: name with - replaced by _).",
        ),
        "python_version": Option(
            None,
            _validate_python_version,
            {"type": "string", "pattern": PYTHON_VERSION_PATTERN.pattern},
            (
                "Python version of the virtual environment "
                "(default: the one that uv chooses, see .python-version and requires-python)."
            ),
        ),
    },
    "paths": {
        "src": _path(None, "Source directory (default: src/<import_name>)."),
        "tests": _path("tests", "Tests directory."),
        "unit_tests": _path(None, "Unit tests (default: <tests>/unit)."),
        "integration_tests": _path(None, "Integration tests (default: <tests>/integration)."),
        "functional_tests": _path(None, "Functional tests (default: <tests>/functional)."),
        "benchmarks": _path(None, "Benchmarks (default: <tests>/benchmarks)."),
        "docs_config": _path("docs/mkdocs.yml", "MkDocs configuration file."),
    },
    "groups": {
        "install": Option(
            ("dev",),
            _normalize_groups,
            _NAMES,
            "Dependency groups of env.install (comma-separated string or list).",
        ),
        "update": Option(
            ("dev", "docs"),
            _normalize_groups,
            _NAMES,
            "Dependency groups of env.update (comma-separated string or list).",
        ),
    },
    "test": {
        "unit_timeout": _timeout(10, "Timeout in seconds of each unit test."),
        "integration_timeout": _timeout(60, "Timeout in seconds of each integration test."),
        "functional_timeout": _timeout(60, "Timeout in seconds of each functional test."),
        "xdoctest": Option(
            True,
            _validate_bool,
            {"type": "boolean"},
            "Run pytest with --xdoctest.",
        ),
        "timeout": Option(
            True,
            _validate_bool,
            {"type": "boolean"},
            "Run pytest with --timeout (it requires pytest-timeout).",
        ),
        "cov_fail_under": Option(
            None,
            _validate_cov_fail_under,
            {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
            "Coverage threshold passed to --cov-fail-under.",
        ),
        "cov_reports": Option(
            ("html", "xml", "term"),
            _validate_cov_reports,
            {
                "anyOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string", "pattern": _COV_REPORT_PATTERN}},
                ]
            },
            "Coverage reports generated by --cov (formats, with an optional :argument).",
        ),
    },
    "types": {
        "checker": Option(
            "ty",
            _validate_checker,
            {"enum": list(TYPE_CHECKERS)},
            "Type checker of types.check and of the types step of check.all.",
        ),
    },
    "check": {
        "tasks": Option(
            None,
            _validate_steps,
            _NAMES,
            "Steps of check.all (comma-separated string or list); null for the default steps.",
        ),
        "cov": Option(
            False,
            _validate_bool,
            {"type": "boolean"},
            "Run the unit step of check.all with --cov, so cov_fail_under is enforced.",
        ),
    },
    "fix": {
        "tasks": Option(
            None,
            _validate_steps,
            _NAMES,
            "Steps of fix.all (comma-separated string or list); null for the default steps.",
        ),
    },
}
r"""The declaration of every key of the ``tasklib`` config, by section.

It is the single source of the known keys, the defaults, the validation
and the JSON schema.
"""

_SECTION_CLASSES: dict[str, type] = get_type_hints(TasklibConfig)
r"""The dataclass of each section of ``SCHEMA``."""


def _defaults(section: str) -> dict[str, object]:
    r"""Return the defaults of a section of ``SCHEMA``.

    Args:
        section: The name of the section.

    Returns:
        A new dict with the default of each key.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._schema import _defaults
    >>> _defaults("groups")
    {'install': ('dev',), 'update': ('dev', 'docs')}

    ```
    """
    return {key: option.default for key, option in SCHEMA[section].items()}


def default_config() -> dict[str, dict[str, object]]:
    r"""Return the defaults of the ``tasklib`` config section.

    The defaults are registered with Invoke (see ``make_ns``) so that
    the keys can also be set with the ``INVOKE_TASKLIB_<SECTION>_<KEY>``
    environment variables, for example ``INVOKE_TASKLIB_PATHS_SRC``.
    Invoke only reads an environment variable for a key that exists in
    the defaults. Invoke casts the variable to the type of the default,
    and it reads any text but ``0`` as true for a boolean, so every key
    is registered with an ``Unset``, which is a string: the text is
    kept and parsed by the validation. The real defaults stay in
    ``SCHEMA``, where ``get_config`` and the JSON schema read them.
    Read the config with ``load_config``, not from ``c.config``: it
    holds an ``Unset`` for a key that no source sets.

    Returns:
        A new dict with the ``package``, ``paths``, ``groups``,
        ``test``, ``types``, ``check`` and ``fix`` sections, with an
        ``Unset`` for every key of ``SCHEMA``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import default_config
    >>> sorted(default_config())
    ['check', 'fix', 'groups', 'package', 'paths', 'test', 'types']
    >>> default_config()["groups"]
    {'install': '', 'update': ''}

    ```
    """
    return {section: {key: Unset() for key in options} for section, options in SCHEMA.items()}


class Unset(str):
    r"""The placeholder of a key that no source sets.

    It is registered as the default of every key, instead of the real
    default, so a ``null`` that a user writes in ``invoke.yaml`` can be
    told from "not set". It is a ``str``, so Invoke does not cast the
    text of an environment variable to the type of the default: the
    text is kept and parsed by the validation.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._schema import Unset
    >>> isinstance(Unset(), str)
    True

    ```
    """

    __slots__ = ()


def json_schema() -> dict[str, Any]:
    r"""Return the JSON schema of the ``tasklib`` config.

    The schema is generated from ``SCHEMA``, so it cannot drift from
    the keys and the defaults. It lets an editor complete and check the
    ``invoke.yaml`` file. Other top-level keys (the config of Invoke
    itself) are allowed.

    Returns:
        The schema, as a dict that can be dumped as JSON.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import json_schema
    >>> schema = json_schema()
    >>> sorted(schema["properties"]["tasklib"]["properties"])
    ['check', 'fix', 'groups', 'package', 'paths', 'test', 'types']

    ```
    """
    sections: dict[str, dict[str, Any]] = {}
    for section, options in SCHEMA.items():
        properties = {}
        for key, option in options.items():
            entry: dict[str, object] = {**option.json_schema, "description": option.doc}
            if option.default is not None:
                default = option.default
                entry["default"] = list(default) if isinstance(default, tuple) else default
            properties[key] = entry
        sections[section] = {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
        }
    sections["package"]["required"] = ["name"]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "invoke.yaml of invoke-tasklib",
        "type": "object",
        "properties": {
            "tasklib": {
                "type": "object",
                "additionalProperties": False,
                "required": ["package"],
                "properties": sections,
            }
        },
    }
