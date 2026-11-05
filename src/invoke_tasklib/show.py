r"""Task that shows the resolved config (``config.show``).

The task is read-only. It validates the config like every other task,
then prints the ``tasklib`` section with the origin of each value. It is
the one task of the ``config`` namespace.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import SCHEMA, load_config
from invoke_tasklib.config._invoke import ENV_LABEL, is_unset, levels, missing_internals
from invoke_tasklib.output import say

if TYPE_CHECKING:
    from invoke.config import Config
    from invoke.context import Context

    from invoke_tasklib.config import TasklibConfig

NAMESPACE = "config"
r"""The name of the namespace of the tasks of this module."""

_PLAIN = re.compile(r"[A-Za-z_][A-Za-z0-9_./-]*")
r"""A string that YAML reads as a plain scalar, so it is not quoted."""

# The plain words that YAML reads as a boolean or as null, so they are
# quoted.
_KEYWORDS = frozenset({"true", "false", "null", "yes", "no", "on", "off", "y", "n", "~"})


@task
def show(c: Context) -> None:
    r"""Show the resolved config and where each value comes from.

    The output is the ``tasklib`` section of ``invoke.yaml`` with every
    key, as the tasks see it, and a comment with the origin of the
    value: ``default``, ``derived`` (computed from other values or from
    the project), ``project file``, ``environment variable
    INVOKE_TASKLIB_...`` and so on. The config is validated first, like
    a task does.

    Args:
        c: The invoke context.
    """
    unknown = missing_internals(c.config)
    if unknown:
        say(
            c,
            f"⚠️  This version of Invoke has no {', '.join(unknown)}: the origin comments "
            "may be wrong, and the check of the current directory is off",
            err=True,
        )
    for line in _render(load_config(c), c.config):
        say(c, line)


def _format_value(value: object) -> str:
    r"""Format a config value as a YAML scalar or a flow sequence.

    Args:
        value: A string, a boolean, an integer, ``None`` or a sequence
            of these.

    Returns:
        The YAML text. A string is quoted unless it is a plain word or
        path, so that ``"3.12"`` is not read as a number.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.show import _format_value
    >>> _format_value("src/pkg")
    'src/pkg'
    >>> _format_value("3.12")
    '"3.12"'
    >>> _format_value(("dev", "docs"))
    '[dev, docs]'
    >>> _format_value(None)
    'null'

    ```
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_value(v) for v in value) + "]"
    if isinstance(value, str) and _PLAIN.fullmatch(value) and value.lower() not in _KEYWORDS:
        return value
    return json.dumps(value)


def _origin(config: Config, section: str, key: str, value: object) -> str:
    r"""Find where a value of the ``tasklib`` config comes from.

    Args:
        config: The invoke config.
        section: The section of the key, e.g. ``"paths"``.
        key: The key, e.g. ``"src"``.
        value: The resolved value of the key.

    Returns:
        The label of the source with the highest priority that sets a
        value for the key (see ``levels``), with the name of the
        variable for an environment variable. If no source sets a
        value, ``"default"`` when the key has a default or the resolved
        value is ``None``, and ``"derived"`` when the value is computed.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke_tasklib.show import _origin
    >>> paths = {"paths": {"src": "lib"}}
    >>> config = Config(overrides={"tasklib": paths})
    >>> _origin(config, "paths", "src", "lib")
    'override'
    >>> _origin(Config(), "paths", "src", "src/pkg")
    'derived'
    >>> _origin(Config(), "test", "cov_fail_under", None)
    'default'
    >>> _origin(Config(), "test", "xdoctest", True)
    'default'

    ```
    """
    for _, label, level in levels(config):
        given = level.get("tasklib", {}).get(section, {}).get(key)
        if given is not None and not is_unset(given):
            if label == ENV_LABEL:
                return f"{label} INVOKE_TASKLIB_{section.upper()}_{key.upper()}"
            return label
    has_default = SCHEMA[section][key].default is not None
    return "default" if value is None or has_default else "derived"


def _render(cfg: TasklibConfig, config: Config) -> list[str]:
    r"""Render the resolved config as YAML lines with the origins.

    Args:
        cfg: The resolved config, see ``get_config``.
        config: The invoke config the values come from.

    Returns:
        The lines: ``tasklib:``, a line per section and a line per
        key, ``key: value  # origin``.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.config import get_config
    >>> from invoke_tasklib.show import _render
    >>> overrides = {"tasklib": {"package": {"name": "demo"}}}
    >>> config = Config(overrides=overrides)
    >>> cfg = get_config(Context(config=config))
    >>> for line in _render(cfg, config)[:4]:
    ...     print(line)
    tasklib:
      package:
        name: demo  # override
        import_name: demo  # derived

    ```
    """
    lines = ["tasklib:"]
    for section, values in asdict(cfg).items():
        lines.append(f"  {section}:")
        lines.extend(
            f"    {key}: {_format_value(value)}  # {_origin(config, section, key, value)}"
            for key, value in values.items()
        )
    return lines
