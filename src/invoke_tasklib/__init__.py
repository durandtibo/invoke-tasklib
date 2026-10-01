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

from invoke.collection import Collection
from invoke.tasks import Task

from invoke_tasklib import (
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

__all__ = [
    "clean",
    "doc",
    "env",
    "format",
    "imports",
    "lint",
    "ns",
    "release",
    "security",
    "test",
    "types",
]

ns: Collection = Collection()
ns.add_collection(Collection.from_module(format), name="format")
ns.add_collection(Collection.from_module(lint), name="lint")
ns.add_collection(Collection.from_module(imports), name="imports")
ns.add_collection(Collection.from_module(types), name="types")
ns.add_collection(Collection.from_module(test), name="test")
ns.add_collection(Collection.from_module(env), name="env")
ns.add_collection(Collection.from_module(release), name="release")
ns.add_collection(Collection.from_module(doc), name="doc")
ns.add_collection(Collection.from_module(security), name="security")
ns.add_task(clean.all, name="clean")  # ty: ignore[invalid-argument-type]
ns.add_task(Task(clean.pycache, name="clean-pycache"))
