r"""The private attributes of the Invoke config.

Invoke has no public API for the sources of the config (the layers that
``config.show`` reports) or for the directory of the loaded
``tasks.py``. This is the only module that reads these private
attributes, so a release of Invoke that renames one is fixed in one
place. A missing attribute is reported, not ignored.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from invoke_tasklib.config._schema import Unset

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

ENV_LABEL = "environment variable"
r"""The label of the layer of the environment variables."""

LEVELS: tuple[tuple[str, str], ...] = (
    ("_defaults", "default"),
    ("_collection", "default"),
    ("_system", "system config file"),
    ("_user", "user config file"),
    ("_project", "project file"),
    ("_env", ENV_LABEL),
    ("_runtime", "runtime config file"),
    ("_overrides", "override"),
    ("_modifications", "override"),
)
r"""The sources of the config, from the lowest to the highest priority:

the attribute of the invoke config and its label.
"""

PROJECT_PREFIX_ATTRIBUTE = "_project_prefix"
r"""The private attribute of the Invoke config that holds the directory
of the loaded ``tasks.py``."""


def project_root(config: object) -> Path | None:
    r"""Return the directory of the loaded ``tasks.py``.

    Args:
        config: The invoke config.

    Returns:
        The resolved directory, or ``None`` if the config has no
        project location (a context created by hand).

    Warns:
        RuntimeWarning: If the config has no ``_project_prefix``
            attribute (a release of Invoke renamed it). The result is
            ``None``, so the check of the current directory is off, and
            the warning says so instead of passing silently.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke_tasklib.config._invoke import project_root
    >>> project_root(Config()) is None
    True

    ```
    """
    if not hasattr(config, PROJECT_PREFIX_ATTRIBUTE):
        warnings.warn(
            f"Cannot check that inv runs from the project root: this version of Invoke has "
            f"no {PROJECT_PREFIX_ATTRIBUTE!r} (please report it)",
            RuntimeWarning,
            stacklevel=3,
        )
        return None
    prefix = getattr(config, PROJECT_PREFIX_ATTRIBUTE)
    return None if prefix is None else Path(prefix).resolve()


def levels(config: object) -> Iterator[tuple[str, str, Mapping]]:
    r"""Iterate over the sources of the config, the highest priority
    first.

    Args:
        config: The invoke config.

    Yields:
        The attribute, the label and the mapping of each source that
        the config has and that is not empty.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke_tasklib.config._invoke import levels
    >>> config = Config(overrides={"tasklib": {}, "x": 1})
    >>> [label for _, label, _ in levels(config)][0]
    'override'

    ```
    """
    for attribute, label in reversed(LEVELS):
        level = getattr(config, attribute, None)
        if level:
            yield attribute, label, level


def missing_internals(config: object) -> list[str]:
    r"""List the private attributes of Invoke that the config lacks.

    ``levels`` and ``project_root`` read them without failing because
    Invoke has no public API for them. If a release of Invoke renames
    one, they would go on without an error: this tells it.

    Args:
        config: The invoke config.

    Returns:
        The names of the missing attributes, in the order of ``LEVELS``,
        then ``_project_prefix``.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke_tasklib.config._invoke import missing_internals
    >>> missing_internals(Config())
    []
    >>> missing_internals(object())[-1]
    '_project_prefix'

    ```
    """
    names = [attribute for attribute, _ in LEVELS] + [PROJECT_PREFIX_ATTRIBUTE]
    return [name for name in names if not hasattr(config, name)]


def is_unset(value: object) -> bool:
    r"""Tell whether a value is the placeholder of a key that no source
    sets.

    Args:
        value: A value of a source of the config.

    Returns:
        ``True`` if the value is an ``Unset``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config._invoke import is_unset
    >>> is_unset(5)
    False

    ```
    """
    return isinstance(value, Unset)
