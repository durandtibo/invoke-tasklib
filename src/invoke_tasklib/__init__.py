r"""Reusable Invoke tasks shared across Python projects.

Typical usage in a consuming project's ``tasks.py``::

    from invoke_tasklib import make_ns

    ns = make_ns()

and an ``invoke.yaml`` at the project root::

    tasklib:
      package:
        name: my_package

To compose a custom subset of tasks, use the ``exclude`` and
``include`` options of ``make_ns``, or import individual task modules
(the module of the ``test`` tasks is ``testing``, so its collection
needs the name ``test`` to keep the task names):

```pycon
>>> from invoke.collection import Collection
>>> from invoke_tasklib import lint, testing
>>> ns = Collection(lint, Collection.from_module(testing, name="test"))
>>> sorted(ns.task_names)
['lint.check-python', 'lint.check-spelling', 'lint.fix-python',
 'lint.pre-commit', 'test.all', 'test.benchmark',
 'test.coverage-report', 'test.doctest', 'test.doctest-markdown',
 'test.doctest-src', 'test.functional', 'test.integration', 'test.unit']

```
"""

from __future__ import annotations

import functools
import importlib.metadata
import warnings
from typing import TYPE_CHECKING, Any

from invoke.collection import Collection

from invoke_tasklib import (
    check,
    clean,
    doc,
    env,
    formatting,
    imports,
    lint,
    release,
    security,
    testing,
    typecheck,
)
from invoke_tasklib.config import default_config

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "__version__",
    "check",
    "clean",
    "doc",
    "env",
    "formatting",
    "imports",
    "lint",
    "make_ns",
    "release",
    "security",
    "testing",
    "typecheck",
]


def _installed_version(distribution: str = "invoke-tasklib") -> str:
    r"""Return the version of an installed distribution.

    Args:
        distribution: The name of the distribution.

    Returns:
        The version, or ``"0+unknown"`` if the distribution is not
        installed (for example when running from a source checkout).

    Example usage:

    ```pycon
    >>> from invoke_tasklib import _installed_version
    >>> _installed_version("no-such-distribution")
    '0+unknown'

    ```
    """
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "0+unknown"


__version__ = _installed_version()
r"""The version of the installed ``invoke-tasklib`` distribution."""

_MODULES = {
    "format": formatting,
    "lint": lint,
    "imports": imports,
    "types": typecheck,
    "test": testing,
    "env": env,
    "release": release,
    "doc": doc,
    "security": security,
    "clean": clean,
    "check": check,
}
r"""The task modules of the default collection, by namespace name."""


def _matches(name: str, patterns: Iterable[str]) -> bool:
    r"""Check whether a task or a namespace is selected by patterns.

    Args:
        name: The dotted name of a task (``"release.pypi"``) or of a
            namespace (``"release"``).
        patterns: Names of namespaces or tasks. A pattern matches the
            name that is equal to it or that is inside it.

    Returns:
        ``True`` if a pattern matches the name.

    Example usage:

    ```pycon
    >>> from invoke_tasklib import _matches
    >>> _matches("release.pypi", ["release"])
    True
    >>> _matches("release.pypi", ["release.build"])
    False

    ```
    """
    return any(name == p or name.startswith(f"{p}.") for p in patterns)


def make_ns(
    *,
    exclude: str | Iterable[str] = (),
    include: str | Iterable[str] | None = None,
) -> Collection:
    r"""Build a new collection of the tasks, optionally restricted.

    Each call returns a new collection, so a project can add its own
    tasks to it or remove some without any effect on other importers
    (unlike ``ns``, which is shared by the process).

    Args:
        exclude: Names of the namespaces (``"doc"``) or of the tasks
            (``"release.pypi"``) to leave out. A single string is one
            name.
        include: Names of the namespaces or of the tasks to keep. If
            ``None``, all the tasks are kept. ``exclude`` is applied
            to what ``include`` keeps. A single string is one name.

    Returns:
        A new collection. The defaults of the ``tasklib`` config are
        registered on it, so that they can be overridden with the
        ``INVOKE_TASKLIB_<SECTION>_<KEY>`` environment variables (for
        example ``INVOKE_TASKLIB_PATHS_SRC``).

    Raises:
        ValueError: If a name of ``exclude`` or ``include`` is not a
            namespace or a task, which is usually a typo.

    Example usage:

    ```pycon
    >>> from invoke_tasklib import make_ns
    >>> ns = make_ns(include=["lint.check-python", "test.unit"])
    >>> sorted(ns.task_names)
    ['lint.check-python', 'test.unit']

    ```
    """
    exclude = (exclude,) if isinstance(exclude, str) else tuple(exclude)
    if isinstance(include, str):
        include = (include,)
    include = None if include is None else tuple(include)
    modules = {
        namespace: Collection.from_module(module, name=namespace)
        for namespace, module in _MODULES.items()
    }
    known = set(modules) | {f"{n}.{t}" for n, sub in modules.items() for t in sub.tasks}
    unknown = sorted((set(exclude) | set(include or ())) - known)
    if unknown:
        msg = f"Unknown task or namespace {unknown}. Valid names: {sorted(known)}"
        raise ValueError(msg)
    ns = Collection()
    for namespace, sub in modules.items():
        selected = Collection(namespace)
        for task_name, task in sub.tasks.items():
            path = f"{namespace}.{task_name}"
            if include is not None and not _matches(path, include):
                continue
            if _matches(path, exclude):
                continue
            selected.add_task(task, name=task_name, default=sub.default == task_name)
        if selected.tasks:
            ns.add_collection(selected)
    ns.configure({"tasklib": default_config()})
    return ns


@functools.cache
def _shared_ns() -> Collection:
    r"""Build the collection that the deprecated ``ns`` returns.

    Returns:
        The same collection on every call, like the former module
        level ``ns``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib import _shared_ns
    >>> _shared_ns() is _shared_ns()
    True

    ```
    """
    return make_ns()


def __getattr__(name: str) -> Any:
    r"""Give the deprecated ``ns`` attribute of the module.

    Args:
        name: The name of the attribute.

    Returns:
        The shared collection, for ``ns``.

    Raises:
        AttributeError: For any other name.
    """
    if name == "ns":
        msg = (
            "'invoke_tasklib.ns' is deprecated and will be removed: it is one collection shared "
            "by every importer. Use 'ns = make_ns()' in your tasks.py instead."
        )
        warnings.warn(msg, DeprecationWarning, stacklevel=2)
        return _shared_ns()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
