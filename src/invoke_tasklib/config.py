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
import json
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from invoke.exceptions import Exit

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from invoke.context import Context


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

    install: tuple[str, ...]
    update: tuple[str, ...]


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
class CheckConfig:
    r"""Resolved ``check`` config section."""

    tasks: tuple[str, ...]


@dataclass(frozen=True)
class TasklibConfig:
    r"""Resolved tasklib config."""

    package: PackageConfig
    paths: PathsConfig
    groups: GroupsConfig
    test: TestConfig
    check: CheckConfig


EXCLUDED_DIRS: frozenset[str] = frozenset({".venv", ".pytest_cache", ".git", "node_modules"})
r"""Directories that the tasks never walk into (not owned by the
project)."""

PYTHON_VERSION_PATTERN = re.compile(r"\d+\.\d+(\.\d+)?")
r"""Pattern of a valid ``package.python_version`` (``3.10`` or
``3.10.4``)."""

COV_REPORTS: frozenset[str] = frozenset(
    {"html", "xml", "json", "lcov", "annotate", "term", "term-missing"}
)
r"""The valid values of ``test.cov_reports`` (the formats of ``--cov-
report`` of pytest-cov)."""

CHECK_STEPS: tuple[str, ...] = (
    "format-python",
    "format-docstrings",
    "lint",
    "types",
    "imports",
    "unit",
    "doctest",
    "shell",
    "spelling",
    "docs",
    "audit",
)
r"""The steps that ``check.all`` can run (``tasklib.check.tasks``)."""


def default_config() -> dict[str, dict[str, object]]:
    r"""Return the defaults of the ``tasklib`` config section.

    The defaults are registered with Invoke (see ``make_ns``) so that
    the keys can also be set with the ``INVOKE_TASKLIB_<SECTION>_<KEY>``
    environment variables, for example ``INVOKE_TASKLIB_PATHS_SRC``.
    Invoke only reads an environment variable for a key that exists in
    the defaults.

    Returns:
        A new dict with the ``package``, ``paths``, ``groups`` and
        ``test`` and ``check`` sections, each a copy of its
        ``DEFAULT_*`` dict.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import default_config
    >>> sorted(default_config())
    ['check', 'groups', 'package', 'paths', 'test']
    >>> default_config()["groups"]
    {'install': 'dev', 'update': 'dev,docs'}

    ```
    """
    return {
        "package": dict(DEFAULT_PACKAGE),
        "paths": dict(DEFAULT_PATHS),
        "groups": dict(DEFAULT_GROUPS),
        "test": dict(DEFAULT_TEST),
        "check": dict(DEFAULT_CHECK),
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


def _normalize_groups(key: str, value: object) -> tuple[str, ...]:
    r"""Normalize a ``groups`` config value to a tuple of names.

    Args:
        key: The name of the config key, used in the error message.
        value: The raw config value: a comma-separated string or a list
            of group names.

    Returns:
        The group names, stripped, without the empty ones.

    Raises:
        ValueError: If the value is neither a string nor a list of
            strings.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _normalize_groups
    >>> _normalize_groups("install", ["dev", "docs"])
    ('dev', 'docs')
    >>> _normalize_groups("install", "dev, docs")
    ('dev', 'docs')

    ```
    """
    if isinstance(value, str):
        names = value.split(",")
    elif isinstance(value, (list, tuple)) and all(isinstance(g, str) for g in value):
        names = list(value)
    else:
        msg = (
            f"'tasklib.groups.{key}' must be a comma-separated string or a list of strings, "
            f"got {value!r}"
        )
        raise ValueError(msg)
    return tuple(name.strip() for name in names if name.strip())


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


def _validate_check_tasks(value: object) -> tuple[str, ...]:
    r"""Validate the ``check.tasks`` config value.

    Args:
        value: The raw config value: a comma-separated string or a list
            of step names.

    Returns:
        The step names, without duplicates, in the order given.

    Raises:
        ValueError: If the value is neither a string nor a list of
            strings, if it is empty, or if a name is not one of
            ``CHECK_STEPS``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _validate_check_tasks
    >>> _validate_check_tasks("lint, unit")
    ('lint', 'unit')
    >>> _validate_check_tasks(["types"])
    ('types',)

    ```
    """
    if isinstance(value, str):
        names = [name.strip() for name in value.split(",")]
    elif isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        names = [name.strip() for name in value]
    else:
        msg = (
            "'tasklib.check.tasks' must be a comma-separated string or a list of "
            f"strings, got {value!r}"
        )
        raise ValueError(msg)
    names = list(dict.fromkeys(name for name in names if name))
    if not names:
        msg = "'tasklib.check.tasks' must contain at least one step"
        raise ValueError(msg)
    unknown = [name for name in names if name not in CHECK_STEPS]
    if unknown:
        msg = (
            f"Unknown check step {unknown} in 'tasklib.check.tasks'. "
            f"Valid steps: {', '.join(CHECK_STEPS)}"
        )
        raise ValueError(msg)
    return tuple(names)


def _validate_cov_fail_under(value: object) -> int | None:
    r"""Validate the ``test.cov_fail_under`` config value.

    Args:
        value: The raw config value: ``None``, an integer, or a string
            of digits (an environment variable).

    Returns:
        ``None`` if the threshold is not set, else the percentage.

    Raises:
        ValueError: If the value is not an integer between 0 and 100.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _validate_cov_fail_under
    >>> _validate_cov_fail_under("90")
    90
    >>> _validate_cov_fail_under(None) is None
    True

    ```
    """
    if value is None:
        return None
    return _validate_int("cov_fail_under", _int_from_text(value), minimum=0, maximum=100)


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


@dataclass(frozen=True)
class Option:
    r"""One key of the ``tasklib`` config: the single place that
    declares it.

    Attributes:
        default: The default value. ``None`` means that the default is
            derived from other values (see ``get_config``) or that the
            key is required. A default is a string for a list, so that
            ``INVOKE_TASKLIB_<SECTION>_<KEY>`` can override it.
        validate: Check a raw value and return the resolved one. It
            raises ``ValueError`` with a message that names the key.
        json_schema: The JSON schema of the key, without ``default``.
        doc: One-line description, used by the JSON schema.
    """

    default: object
    validate: Callable[[object], object]
    json_schema: Mapping[str, object]
    doc: str = ""


_STRING = {"type": "string", "minLength": 1}
_NAMES = {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}


def _timeout(key: str, default: int, doc: str) -> Option:
    r"""Declare a per-test timeout key of the ``test`` section.

    Args:
        key: The name of the key.
        default: The timeout in seconds.
        doc: The description of the key.

    Returns:
        The option.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _timeout
    >>> _timeout("unit_timeout", 10, "Timeout.").default
    10

    ```
    """
    return Option(
        default,
        partial(_validate_int, key, minimum=1),
        {"type": "integer", "minimum": 1},
        doc,
    )


def _path(key: str, default: str | None, doc: str) -> Option:
    r"""Declare a key of the ``paths`` section.

    Args:
        key: The name of the key.
        default: The default path, or ``None`` if it is derived.
        doc: The description of the key.

    Returns:
        The option.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _path
    >>> _path("tests", "tests", "Tests.").default
    'tests'

    ```
    """
    return Option(default, partial(_validate_str, "paths", key), _STRING, doc)


SCHEMA: dict[str, dict[str, Option]] = {
    "package": {
        "name": Option(
            None,
            partial(_validate_str, "package", "name"),
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
            "3.14",
            _validate_python_version,
            {"type": "string", "pattern": PYTHON_VERSION_PATTERN.pattern},
            "Python version of the virtual environment (quote it in YAML).",
        ),
    },
    "paths": {
        "src": _path("src", None, "Source directory (default: src/<import_name>)."),
        "tests": _path("tests", "tests", "Tests directory."),
        "unit_tests": _path("unit_tests", None, "Unit tests (default: <tests>/unit)."),
        "integration_tests": _path(
            "integration_tests", None, "Integration tests (default: <tests>/integration)."
        ),
        "functional_tests": _path(
            "functional_tests", None, "Functional tests (default: <tests>/functional)."
        ),
        "benchmarks": _path("benchmarks", None, "Benchmarks (default: <tests>/benchmarks)."),
        "docs_config": _path("docs_config", "docs/mkdocs.yml", "MkDocs configuration file."),
    },
    "groups": {
        "install": Option(
            "dev",
            partial(_normalize_groups, "install"),
            _NAMES,
            "Dependency groups of env.install (comma-separated string or list).",
        ),
        "update": Option(
            "dev,docs",
            partial(_normalize_groups, "update"),
            _NAMES,
            "Dependency groups of env.update (comma-separated string or list).",
        ),
    },
    "test": {
        "unit_timeout": _timeout("unit_timeout", 10, "Timeout in seconds of each unit test."),
        "integration_timeout": _timeout(
            "integration_timeout", 60, "Timeout in seconds of each integration test."
        ),
        "functional_timeout": _timeout(
            "functional_timeout", 60, "Timeout in seconds of each functional test."
        ),
        "xdoctest": Option(
            True,
            partial(_validate_bool, "xdoctest"),
            {"type": "boolean"},
            "Run pytest with --xdoctest.",
        ),
        "cov_fail_under": Option(
            None,
            _validate_cov_fail_under,
            {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
            "Coverage threshold passed to --cov-fail-under.",
        ),
        "cov_reports": Option(
            "html,xml,term",
            _validate_cov_reports,
            {
                "anyOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"enum": sorted(COV_REPORTS)}},
                ]
            },
            "Coverage report formats generated by --cov.",
        ),
    },
    "check": {
        "tasks": Option(
            "format-python,format-docstrings,lint,types,imports,unit",
            _validate_check_tasks,
            {
                "anyOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"enum": list(CHECK_STEPS)}},
                ]
            },
            "Steps of check.all (comma-separated string or list).",
        ),
    },
}
r"""The declaration of every key of the ``tasklib`` config, by section.

It is the single source of the known keys, the defaults, the
validation and the JSON schema."""

_SECTION_CLASSES: dict[str, type] = {
    "package": PackageConfig,
    "paths": PathsConfig,
    "groups": GroupsConfig,
    "test": TestConfig,
    "check": CheckConfig,
}
r"""The dataclass of each section of ``SCHEMA``."""


def _defaults(section: str) -> dict[str, object]:
    r"""Return the defaults of a section of ``SCHEMA``.

    Args:
        section: The name of the section.

    Returns:
        A new dict with the default of each key.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import _defaults
    >>> _defaults("groups")
    {'install': 'dev', 'update': 'dev,docs'}

    ```
    """
    return {key: option.default for key, option in SCHEMA[section].items()}


DEFAULT_PACKAGE: dict[str, object] = _defaults("package")
r"""Defaults of the ``package`` section."""

DEFAULT_PATHS: dict[str, object] = _defaults("paths")
r"""Defaults of the ``paths`` section."""

DEFAULT_GROUPS: dict[str, object] = _defaults("groups")
r"""Defaults of the ``groups`` section."""

DEFAULT_TEST: dict[str, object] = _defaults("test")
r"""Defaults of the ``test`` section."""

DEFAULT_CHECK: dict[str, object] = _defaults("check")
r"""Defaults of the ``check`` section."""


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
    ['check', 'groups', 'package', 'paths', 'test']

    ```
    """
    sections: dict[str, dict[str, Any]] = {}
    for section, options in SCHEMA.items():
        properties = {}
        for key, option in options.items():
            entry: dict[str, object] = {**option.json_schema, "description": option.doc}
            if option.default is not None:
                entry["default"] = option.default
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


def main(argv: Sequence[str]) -> int:
    r"""Print the JSON schema of the ``tasklib`` config.

    It is run with ``python -m invoke_tasklib.config``.

    Args:
        argv: The command line arguments, without the program name.
            There must be none.

    Returns:
        The exit code: 0 on success, 2 if there are arguments.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config import main
    >>> _ = main(["--bad"])
    usage: python -m invoke_tasklib.config

    ```
    """
    if argv:
        sys.stdout.write("usage: python -m invoke_tasklib.config\n")
        return 2
    sys.stdout.write(json.dumps(json_schema(), indent=2) + "\n")
    return 0


def get_config(c: Context) -> TasklibConfig:
    r"""Return the effective tasklib config, merging user overrides from
    ``invoke.yaml`` (under the ``tasklib`` key) on top of the defaults.

    Args:
        c: The invoke context.

    Returns:
        A frozen dataclass with the resolved ``package``, ``paths``,
        ``groups``, ``test`` and ``check`` sections, each a frozen
        dataclass too,
        e.g. ``cfg.paths.src``.

    Raises:
        ValueError: If ``tasklib`` or one of its sections (``package``,
            ``paths``, ``groups``, ``test`` and ``check``) is not a
            mapping, or if ``tasklib`` or a section has an unknown key
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
            ``tasklib.check.tasks`` is empty or has an unknown step.

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
    package, paths = merged["package"], merged["paths"]

    if not package["name"]:
        msg = "'tasklib.package.name' must be set in invoke.yaml"
        raise ValueError(msg)
    name = _validate_str("package", "name", package["name"])
    if package["import_name"] is None:
        package["import_name"] = name.replace("-", "_")
    if paths["src"] is None:
        paths["src"] = _default_src(_validate_import_name(package["import_name"]))
    for key, scope in _TEST_SCOPES.items():
        if paths[key] is None:
            paths[key] = f"{paths['tests']}/{scope}"

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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
