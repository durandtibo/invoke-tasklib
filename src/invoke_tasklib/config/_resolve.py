r"""Resolution of the tasklib config from the Invoke config."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from invoke.exceptions import Exit

from invoke_tasklib.config._derive import _derive_defaults
from invoke_tasklib.config._schema import (
    _SECTION_CLASSES,
    SCHEMA,
    TasklibConfig,
    _defaults,
)
from invoke_tasklib.config._validate import _as_mapping, _check_keys, _validate_str

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
        ValueError: If the config is invalid: an unknown key, a missing
            ``tasklib.package.name`` or a value that is not valid. The
            message names the key. The rules of every key are listed in
            the user guide, see ``uguide/config.md``.

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


def _check_project_root(c: Context) -> None:
    r"""Check that Invoke runs from the directory of ``tasks.py``.

    Invoke looks for ``tasks.py`` in the parents of the current
    directory and loads the ``invoke.yaml`` next to it, but it does not
    change directory. The tasks use paths relative to the current
    directory (``tests/unit``, ``pyproject.toml``, ``dist``, ...), so
    they would look in the wrong place, and skip a missing directory
    silently.

    Args:
        c: The invoke context. A context that has no project location
            (a context created by hand) is not checked.

    Raises:
        ValueError: If the current directory is not the directory of
            the loaded ``tasks.py``. The message tells how to fix it.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.config._resolve import _check_project_root
    >>> _check_project_root(Context(config=Config()))

    ```
    """
    prefix = getattr(c.config, "_project_prefix", None)
    if prefix is None:
        return
    root = Path(prefix).resolve()
    cwd = Path.cwd().resolve()
    if root != cwd:
        msg = (
            f"inv must run from the project root, where tasks.py is: {root} "
            f"(the current directory is {cwd}). Run 'cd {root}' first."
        )
        raise ValueError(msg)


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
        Exit: If ``get_config`` raises a ``ValueError``, or if Invoke
            runs from another directory than the one of ``tasks.py``.
            The message is the one of the ``ValueError``.

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
        _check_project_root(c)
        return get_config(c)
    except ValueError as exc:
        raise Exit(str(exc), code=2) from exc
