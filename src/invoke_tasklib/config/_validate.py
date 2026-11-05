r"""Validation of the values of the config."""

from __future__ import annotations

import difflib
from collections.abc import Mapping
from typing import TYPE_CHECKING

from invoke_tasklib.config._constants import (
    COV_REPORTS,
    PYTHON_VERSION_PATTERN,
    TYPE_CHECKERS,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


def _validate_checker(path: str, value: object) -> str:
    r"""Validate the ``types.checker`` config value.

    Args:
        path: The dotted name of the config key, used in the error
            message, e.g. ``"tasklib.types.checker"``.
        value: The raw config value.

    Returns:
        The validated type checker.

    Raises:
        ValueError: If the value is not one of ``TYPE_CHECKERS``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import _validate_checker
    >>> _validate_checker("tasklib.types.checker", "mypy")
    'mypy'

    ```
    """
    if value not in TYPE_CHECKERS:
        msg = f"'{path}' must be one of {', '.join(TYPE_CHECKERS)}, got {value!r}"
        raise ValueError(msg)
    return str(value)


def _validate_python_version(path: str, value: object) -> str | None:
    r"""Validate the ``package.python_version`` config value.

    YAML reads an unquoted ``3.10`` as the float ``3.1``, which would
    silently select the wrong Python version, so only quoted strings
    such as ``"3.10"`` or ``"3.10.4"`` are accepted.

    Args:
        path: The dotted name of the config key, used in the error
            message, e.g. ``"tasklib.package.python_version"``.
        value: The raw config value, or ``None`` if it is not set.

    Returns:
        The validated version string, or ``None`` if the value is not
        set: ``uv`` then chooses the Python version.

    Raises:
        ValueError: If the value is set and is not a string like
            ``"3.10"`` or ``"3.10.4"``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import (
    ...     _validate_python_version,
    ... )
    >>> path = "tasklib.package.python_version"
    >>> _validate_python_version(path, "3.10")
    '3.10'
    >>> _validate_python_version(path, None) is None
    True

    ```
    """
    if value is None:
        return None
    if not isinstance(value, str) or not PYTHON_VERSION_PATTERN.fullmatch(value):
        msg = (
            f'\'{path}\' must be a string like "3.10" or "3.10.4", '
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
    >>> from invoke_tasklib.config._validate import _as_mapping
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
            ``groups``, ``test``, ``types``, ``check`` or ``fix``),
            used in the error message. An empty string stands for the
            ``tasklib`` section itself.
        user: The user values of the section.
        valid: The valid keys of the section.

    Raises:
        ValueError: If ``user`` has keys that are not in ``valid``. The
            message lists the unknown keys, with the closest valid key
            when there is one, and the valid keys.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import _check_keys
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


def _as_names(key_path: str, value: object) -> list[str]:
    r"""Convert a list-like config value to a list of names.

    Args:
        key_path: The full name of the config key, used in the error
            message, e.g. ``"tasklib.groups.install"``.
        value: The raw config value: a comma-separated string or a list
            (or tuple) of strings.

    Returns:
        The names, stripped, without the empty ones and without
        duplicates, in the order given.

    Raises:
        ValueError: If the value is neither a string nor a list of
            strings.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import _as_names
    >>> _as_names("tasklib.groups.install", "dev, docs,dev")
    ['dev', 'docs']
    >>> _as_names("tasklib.groups.install", ["dev", " "])
    ['dev']

    ```
    """
    if isinstance(value, str):
        names = value.split(",")
    elif isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        names = list(value)
    else:
        msg = f"'{key_path}' must be a comma-separated string or a list of strings, got {value!r}"
        raise ValueError(msg)
    return list(dict.fromkeys(name.strip() for name in names if name.strip()))


def _normalize_groups(path: str, value: object) -> tuple[str, ...]:
    r"""Normalize a ``groups`` config value to a tuple of names.

    Args:
        path: The dotted name of the config key, used in the error
            message, e.g. ``"tasklib.groups.install"``.
        value: The raw config value: a comma-separated string or a list
            of group names.

    Returns:
        The group names, stripped, without the empty ones and without
        duplicates.

    Raises:
        ValueError: If the value is neither a string nor a list of
            strings.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import _normalize_groups
    >>> _normalize_groups("tasklib.groups.install", ["dev", "docs"])
    ('dev', 'docs')
    >>> _normalize_groups("tasklib.groups.install", "dev, docs")
    ('dev', 'docs')

    ```
    """
    return tuple(_as_names(path, value))


def _validate_import_name(path: str, value: object) -> str:
    r"""Validate the ``package.import_name`` config value.

    Args:
        path: The dotted name of the config key, used in the error
            message, e.g. ``"tasklib.package.import_name"``.
        value: The raw config value.

    Returns:
        The validated import name.

    Raises:
        ValueError: If the value is not a string of Python identifiers
            separated by dots, e.g. ``"my_package"``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import (
    ...     _validate_import_name,
    ... )
    >>> path = "tasklib.package.import_name"
    >>> _validate_import_name(path, "my_package")
    'my_package'

    ```
    """
    if not isinstance(value, str) or not all(part.isidentifier() for part in value.split(".")):
        msg = f"'{path}' must be a Python module name such as \"my_package\", got {value!r}"
        raise ValueError(msg)
    return value


_BOOL_TEXT: dict[str, bool] = {
    "true": True,
    "1": True,
    "yes": True,
    "on": True,
    "false": False,
    "0": False,
    "no": False,
    "off": False,
}
r"""The spellings of a boolean in an environment variable."""


def _validate_int(path: str, value: object, *, minimum: int, maximum: int | None = None) -> int:
    r"""Validate an integer value of a config section.

    Args:
        path: The dotted name of the config key, used in the error
            message, e.g. ``"tasklib.test.unit_timeout"``.
        value: The raw config value: an integer or a string of digits
            (an environment variable).
        minimum: The smallest valid value.
        maximum: The largest valid value, or ``None`` for no limit.

    Returns:
        The validated integer.

    Raises:
        ValueError: If the value is not an integer or a string of
            digits (a boolean is not accepted), is smaller than
            ``minimum`` or is larger than ``maximum``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import _validate_int
    >>> _validate_int("tasklib.test.unit_timeout", 10, minimum=1)
    10
    >>> _validate_int("tasklib.test.unit_timeout", "10", minimum=1)
    10

    ```
    """
    number = _int_from_text(value)
    if (
        isinstance(number, bool)
        or not isinstance(number, int)
        or number < minimum
        or (maximum is not None and number > maximum)
    ):
        bounds = f">= {minimum}" if maximum is None else f"between {minimum} and {maximum}"
        msg = f"'{path}' must be an integer {bounds}, got {value!r}"
        raise ValueError(msg)
    return number


def _validate_str(path: str, value: object) -> str:
    r"""Validate a non-empty string value of the config.

    It checks ``package.name`` and the keys of the ``paths`` section.

    Args:
        path: The dotted name of the config key, used in the error
            message, e.g. ``"tasklib.paths.src"``.
        value: The raw config value.

    Returns:
        The validated string.

    Raises:
        ValueError: If the value is not a string, or is empty.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import _validate_str
    >>> _validate_str("tasklib.paths.src", "src/mypkg")
    'src/mypkg'

    ```
    """
    if not isinstance(value, str) or not value:
        msg = f"'{path}' must be a non-empty string, got {value!r}"
        raise ValueError(msg)
    return value


def _int_from_text(value: object) -> object:
    r"""Convert a string of digits to an integer.

    Invoke reads an environment variable as a string. The keys are
    registered with an ``Unset`` (see ``default_config``), so
    ``INVOKE_TASKLIB_TEST_UNIT_TIMEOUT=30`` is the string ``"30"``.

    Args:
        value: The raw config value.

    Returns:
        The integer if ``value`` is a string of ASCII digits, ``value``
        unchanged otherwise.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import _int_from_text
    >>> _int_from_text("90")
    90
    >>> _int_from_text(90)
    90

    ```
    """
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return value


def _is_cov_report(name: str) -> bool:
    r"""Check a ``--cov-report`` value of pytest-cov.

    Args:
        name: The value, e.g. ``"html"`` or ``"xml:cov.xml"``.

    Returns:
        ``True`` if the part before the first colon is one of
        ``COV_REPORTS`` and, when there is a colon, something follows
        it.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import _is_cov_report
    >>> _is_cov_report("term-missing:skip-covered")
    True
    >>> _is_cov_report("html:")
    False

    ```
    """
    report, colon, argument = name.partition(":")
    return report in COV_REPORTS and (not colon or bool(argument))


def _validate_cov_reports(path: str, value: object) -> tuple[str, ...]:
    r"""Validate the ``test.cov_reports`` config value.

    Args:
        path: The dotted name of the config key, used in the error
            message, e.g. ``"tasklib.test.cov_reports"``.
        value: The raw config value: a comma-separated string or a list
            of ``--cov-report`` values. A value is a format of
            ``COV_REPORTS`` with an optional ``:<argument>``, as in
            ``term-missing:skip-covered`` or ``html:cov_html``.

    Returns:
        The values, without duplicates, in the order given. They are
        not changed: the argument is kept.

    Raises:
        ValueError: If the value is neither a string nor a list of
            strings, if a format is not one of ``COV_REPORTS``, or if
            an argument after the colon is empty.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import (
    ...     _validate_cov_reports,
    ... )
    >>> _validate_cov_reports("tasklib.test.cov_reports", "html, term")
    ('html', 'term')
    >>> _validate_cov_reports("tasklib.test.cov_reports", ["xml"])
    ('xml',)
    >>> _validate_cov_reports(
    ...     "tasklib.test.cov_reports", "term-missing:skip-covered"
    ... )
    ('term-missing:skip-covered',)

    ```
    """
    names = _as_names(path, value)
    unknown = [name for name in names if not _is_cov_report(name)]
    if unknown:
        msg = (
            f"Unknown coverage report {unknown} in '{path}'. "
            f"Valid reports: {', '.join(sorted(COV_REPORTS))}"
        )
        raise ValueError(msg)
    return tuple(names)


def _validate_steps(path: str, value: object) -> tuple[str, ...] | None:
    r"""Validate the ``tasks`` value of a section that lists steps.

    Only the shape is checked here. The names are checked by the
    composite task (``check.all`` or ``fix.all``), which is the only
    place that lists the steps.

    Args:
        path: The dotted name of the config key, e.g.
            ``"tasklib.check.tasks"``.
        value: The raw config value: ``None`` for the default steps, a
            comma-separated string or a list of step names.

    Returns:
        ``None`` for the default steps, else the step names, without
        duplicates, in the order given.

    Raises:
        ValueError: If the value is neither ``None``, a string nor a
            list of strings, or if it is empty.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import _validate_steps
    >>> path = "tasklib.fix.tasks"
    >>> _validate_steps(path, "lint, unit")
    ('lint', 'unit')
    >>> _validate_steps(path, None) is None
    True

    ```
    """
    if value is None:
        return None
    names = _as_names(path, value)
    if not names:
        msg = f"'{path}' must contain at least one step"
        raise ValueError(msg)
    return tuple(names)


def _validate_cov_fail_under(path: str, value: object) -> int | None:
    r"""Validate the ``test.cov_fail_under`` config value.

    Args:
        path: The dotted name of the config key, used in the error
            message, e.g. ``"tasklib.test.cov_fail_under"``.
        value: The raw config value: ``None``, an integer, or a string
            of digits (an environment variable).

    Returns:
        ``None`` if the threshold is not set, else the percentage.

    Raises:
        ValueError: If the value is not an integer between 0 and 100.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import (
    ...     _validate_cov_fail_under,
    ... )
    >>> path = "tasklib.test.cov_fail_under"
    >>> _validate_cov_fail_under(path, "90")
    90
    >>> _validate_cov_fail_under(path, None) is None
    True

    ```
    """
    if value is None:
        return None
    return _validate_int(path, value, minimum=0, maximum=100)


def _validate_bool(path: str, value: object) -> bool:
    r"""Validate a boolean value of a config section.

    Args:
        path: The dotted name of the config key, used in the error
            message, e.g. ``"tasklib.test.xdoctest"``.
        value: The raw config value: a boolean or a string (an
            environment variable) that is one of ``true``, ``false``,
            ``1``, ``0``, ``yes``, ``no``, ``on`` and ``off``, in any
            case.

    Returns:
        The validated boolean.

    Raises:
        ValueError: If the value is neither a boolean nor one of the
            accepted strings.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._validate import _validate_bool
    >>> _validate_bool("tasklib.test.xdoctest", False)
    False
    >>> _validate_bool("tasklib.test.xdoctest", "no")
    False

    ```
    """
    if isinstance(value, str):
        value = _BOOL_TEXT.get(value.lower(), value)
    if value is not True and value is not False:
        msg = f"'{path}' must be a boolean (true or false), got {value!r}"
        raise ValueError(msg)
    return value
