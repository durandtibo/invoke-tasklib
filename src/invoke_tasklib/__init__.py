r"""Reusable Invoke tasks shared across Python projects.

Typical usage in a consuming project's ``tasks.py``::

    from invoke_tasklib import ns

and an ``invoke.yaml`` at the project root::

    tasklib:
      package:
        name: my_package

To compose a custom subset of tasks instead of using the default
``ns``, import individual task modules:

```pycon
>>> from invoke.collection import Collection
>>> from invoke_tasklib import lint, test
>>> ns = Collection(lint, test)
>>> sorted(ns.task_names)
['lint.check-python', 'lint.fix-python', 'test.all', 'test.benchmark',
 'test.coverage-report', 'test.doctest', 'test.doctest-markdown',
 'test.doctest-src', 'test.functional', 'test.integration', 'test.unit']

```
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.collection import Collection

from invoke_tasklib import (
    check,
    clean,
    doc,
    env,
    format,  # noqa: A004
    imports,
    lint,
    release,
    security,
    test,
    types,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "check",
    "clean",
    "doc",
    "env",
    "format",
    "imports",
    "lint",
    "make_ns",
    "ns",
    "release",
    "security",
    "test",
    "types",
]

_MODULES = {
    "format": format,
    "lint": lint,
    "imports": imports,
    "types": types,
    "test": test,
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


def make_ns(*, exclude: Iterable[str] = (), include: Iterable[str] | None = None) -> Collection:
    r"""Build a new collection of the tasks, optionally restricted.

    Each call returns a new collection, so a project can add its own
    tasks to it or remove some without any effect on other importers
    (unlike ``ns``, which is shared by the process).

    Args:
        exclude: Names of the namespaces (``"doc"``) or of the tasks
            (``"release.pypi"``) to leave out.
        include: Names of the namespaces or of the tasks to keep. If
            ``None``, all the tasks are kept. ``exclude`` is applied
            to what ``include`` keeps.

    Returns:
        A new collection.

    Raises:
        ValueError: If a name of ``exclude`` or ``include`` is not a
            namespace or a task, which is usually a typo.

    Example usage:

    ```pycon
    >>> from invoke_tasklib import make_ns
    >>> ns = make_ns(include=["lint", "test.unit"], exclude=["lint.fix-python"])
    >>> sorted(ns.task_names)
    ['lint.check-python', 'test.unit']

    ```
    """
    exclude = tuple(exclude)
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
    return ns


ns: Collection = make_ns()
