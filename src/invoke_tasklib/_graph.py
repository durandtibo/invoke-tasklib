r"""Static import graph of a package, and its cycles.

The graph is built from the source files with ``ast``, so no module is
imported and the result does not depend on the order of the imports.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from invoke_tasklib._discover import discover_modules, find_spec

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Mapping


def _is_type_checking(test: ast.expr) -> bool:
    r"""Check whether the test of an ``if`` is ``TYPE_CHECKING``.

    Args:
        test: The expression of the ``if``.

    Returns:
        ``True`` for ``TYPE_CHECKING`` and ``<name>.TYPE_CHECKING``.

    Example usage:

    ```pycon
    >>> import ast
    >>> from invoke_tasklib._graph import _is_type_checking
    >>> def test(code):
    ...     return _is_type_checking(ast.parse(code, mode="eval").body)
    >>> test("typing.TYPE_CHECKING")
    True
    >>> test("DEBUG")
    False

    ```
    """
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


class _ImportCollector(ast.NodeVisitor):
    r"""Collect the imports of a module.

    Args:
        package: The package that relative imports are relative to
            (the module itself if it is a package).
        lazy: If True, also collect the imports inside functions.
        type_checking: If True, also collect the imports under
            ``if TYPE_CHECKING:``.
        filename: The name of the module, used in the error of a
            relative import that goes above the top-level package.

    Raises:
        SyntaxError: If a relative import goes above the top-level
            package, like Python does (``attempted relative import
            beyond top-level package``).
    """

    def __init__(
        self, package: str, *, lazy: bool, type_checking: bool, filename: str = "<unknown>"
    ) -> None:
        r"""Initialize the collector with the options."""
        self.package = package
        self.filename = filename
        self.lazy = lazy
        self.type_checking = type_checking
        self.found: list[tuple[str, tuple[str, ...]]] = []

    def visit_Import(self, node: ast.Import) -> None:
        r"""Collect ``import a.b``."""
        self.found.extend((alias.name, ()) for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        r"""Collect ``from a import b`` and its relative forms."""
        base: list[str] = []
        if node.level:
            package = self.package.split(".") if self.package else []
            if node.level > len(package):
                msg = "attempted relative import beyond top-level package"
                raise SyntaxError(msg, (self.filename, node.lineno, node.col_offset + 1, None))
            base = package[: len(package) - (node.level - 1)]
        parts = [*base, *(node.module.split(".") if node.module else [])]
        self.found.append((".".join(parts), tuple(alias.name for alias in node.names)))

    def visit_If(self, node: ast.If) -> None:
        r"""Skip the ``TYPE_CHECKING`` branch unless asked."""
        if _is_type_checking(node.test) and not self.type_checking:
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        r"""Skip the body of a function unless asked."""
        if self.lazy:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        r"""Skip the body of an async function unless asked."""
        if self.lazy:
            self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        r"""Skip the body of a lambda unless asked."""
        if self.lazy:
            self.generic_visit(node)


def parse_imports(
    source: str,
    module: str,
    *,
    is_package: bool = False,
    lazy: bool = False,
    type_checking: bool = False,
) -> list[tuple[str, tuple[str, ...]]]:
    r"""List the imports of a module, with absolute names.

    Args:
        source: The source code of the module.
        module: The dotted name of the module.
        is_package: Whether the module is the ``__init__`` of a
            package, which changes what a relative import is relative
            to.
        lazy: If True, also list the imports inside functions (they
            are run when the function is called, not when the module is
            imported). By default they are ignored.
        type_checking: If True, also list the imports under ``if
            TYPE_CHECKING:`` (never run). By default they are ignored.

    Returns:
        A ``(module, names)`` pair per import statement, in the order
        of the source. ``names`` is empty for ``import a.b`` and has
        the imported names for ``from a.b import c, d``.

    Raises:
        SyntaxError: If ``source`` is not valid Python, or if a
            relative import goes above the top-level package. Its
            ``filename`` is the name of the module.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._graph import parse_imports
    >>> parse_imports("import os\nfrom . import b\n", "pkg.a")
    [('os', ()), ('pkg', ('b',))]

    ```
    """
    package = module if is_package else module.rpartition(".")[0]
    collector = _ImportCollector(package, lazy=lazy, type_checking=type_checking, filename=module)
    collector.visit(ast.parse(source, filename=module))
    return collector.found


def _resolve(name: str, known: Collection[str]) -> str | None:
    r"""Find the module of the package that a dotted name designates.

    Args:
        name: A dotted name, e.g. ``"pkg.sub.attr"``.
        known: The modules of the package.

    Returns:
        The longest prefix of ``name`` that is a known module, or
        ``None`` if there is none.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._graph import _resolve
    >>> _resolve("pkg.a.X", {"pkg", "pkg.a"})
    'pkg.a'
    >>> _resolve("os.path", {"pkg"}) is None
    True

    ```
    """
    parts = name.split(".")
    for end in range(len(parts), 0, -1):
        candidate = ".".join(parts[:end])
        if candidate in known:
            return candidate
    return None


def import_graph(
    sources: Mapping[str, str],
    packages: Collection[str] = (),
    *,
    lazy: bool = False,
    type_checking: bool = False,
) -> dict[str, set[str]]:
    r"""Build the import graph of the modules of a package.

    ``import a.b`` is an edge to ``a.b``, and ``from a import b`` is an
    edge to ``a.b`` if it is a module, else to ``a``. Imports of
    modules outside of ``sources`` and imports of a module by itself are
    not edges.

    Args:
        sources: The source code of each module, by dotted name.
        packages: The names of the modules that are packages.
        lazy: See ``parse_imports``.
        type_checking: See ``parse_imports``.

    Returns:
        The set of modules imported by each module of ``sources``.

    Raises:
        SyntaxError: If a source is not valid Python.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._graph import import_graph
    >>> src = {"p.a": "from p import b", "p.b": "import p.a", "p": ""}
    >>> import_graph(src, ["p"])["p.a"]
    {'p.b'}

    ```
    """
    graph: dict[str, set[str]] = {}
    for module, source in sources.items():
        edges: set[str] = set()
        imports = parse_imports(
            source, module, is_package=module in packages, lazy=lazy, type_checking=type_checking
        )
        for name, names in imports:
            targets = [f"{name}.{n}" for n in names if f"{name}.{n}" in sources]
            edges.update(
                target
                for target in (targets or [_resolve(name, sources)])
                if target is not None and target != module
            )
        graph[module] = edges
    return graph


class _Tarjan:
    r"""Tarjan's algorithm for the strongly connected components.

    It uses an explicit stack of iterators instead of recursion, so a
    long chain of modules cannot hit the recursion limit.

    Args:
        graph: The nodes that each node points to. Every target must
            be a key.
    """

    def __init__(self, graph: Mapping[str, Collection[str]]) -> None:
        r"""Initialize the search on a graph."""
        self.graph = graph
        self.index: dict[str, int] = {}
        self.low: dict[str, int] = {}
        self.stack: list[str] = []
        self.on_stack: set[str] = set()
        self.found: list[list[str]] = []

    def _push(self, node: str) -> tuple[str, Iterator[str]]:
        r"""Visit a node for the first time."""
        self.index[node] = self.low[node] = len(self.index)
        self.stack.append(node)
        self.on_stack.add(node)
        return node, iter(sorted(self.graph[node]))

    def _pop_component(self, root: str) -> None:
        r"""Close the component of a root (kept if it is a cycle)."""
        component: list[str] = []
        while not component or component[-1] != root:
            component.append(self.stack.pop())
        self.on_stack.difference_update(component)
        if len(component) > 1:
            self.found.append(sorted(component))

    def _advance(self, work: list[tuple[str, Iterator[str]]]) -> None:
        r"""Do one step of the search on the top of ``work``."""
        node, children = work[-1]
        child = next((c for c in children if c not in self.index or c in self.on_stack), None)
        if child is None:
            work.pop()
            if work:
                parent = work[-1][0]
                self.low[parent] = min(self.low[parent], self.low[node])
            if self.low[node] == self.index[node]:
                self._pop_component(node)
        elif child not in self.index:
            work.append(self._push(child))
        else:
            self.low[node] = min(self.low[node], self.index[child])

    def run(self) -> list[list[str]]:
        r"""Find the components of at least two nodes.

        Returns:
            The components, each sorted, and sorted among them.
        """
        for start in sorted(self.graph):
            if start not in self.index:
                work = [self._push(start)]
                while work:
                    self._advance(work)
        return sorted(self.found)


def _components(graph: Mapping[str, Collection[str]]) -> list[list[str]]:
    r"""Find the strongly connected components of a graph.

    Args:
        graph: The nodes that each node points to. Every target must
            be a key.

    Returns:
        The components of at least two nodes, each sorted, and sorted
        among them.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._graph import _components
    >>> _components({"a": ["b"], "b": ["a", "c"], "c": []})
    [['a', 'b']]

    ```
    """
    return _Tarjan(graph).run()


def _cycle_in(component: list[str], graph: Mapping[str, Collection[str]]) -> list[str]:
    r"""Find one cycle of a strongly connected component.

    Args:
        component: The sorted nodes of the component.
        graph: The nodes that each node points to.

    Returns:
        The shortest cycle that goes through the first node of the
        component, as a path that starts and ends on it.

    Raises:
        ValueError: If no cycle goes through the first node.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._graph import _cycle_in
    >>> _cycle_in(["a", "b", "c"], {"a": ["b"], "b": ["c"], "c": ["a"]})
    ['a', 'b', 'c', 'a']

    ```
    """
    start = component[0]
    members = set(component)
    previous: dict[str, str] = {}
    queue = [start]
    for node in queue:
        for child in sorted(graph[node]):
            if child == start:
                path = [node]
                while path[-1] != start:
                    path.append(previous[path[-1]])
                return [start, *reversed(path[:-1]), start]
            if child in members and child not in previous:
                previous[child] = node
                queue.append(child)
    msg = f"No cycle goes through {start!r}: not a strongly connected component"
    raise ValueError(msg)


def find_cycles(graph: Mapping[str, Collection[str]]) -> list[list[str]]:
    r"""Find the import cycles of a graph.

    Args:
        graph: The nodes that each node points to. Every target must
            be a key.

    Returns:
        One cycle per strongly connected component (so a group of
        entangled cycles is reported once), as a path that starts and
        ends on the same node, e.g. ``["a", "b", "a"]``. The result is
        sorted, so it is the same on every run.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._graph import find_cycles
    >>> find_cycles({"a": ["b"], "b": ["a"], "c": ["a"]})
    [['a', 'b', 'a']]
    >>> find_cycles({"a": ["b"], "b": []})
    []

    ```
    """
    return [_cycle_in(component, graph) for component in _components(graph)]


def read_sources(name: str) -> tuple[dict[str, str], set[str]]:
    r"""Read the source of every module of a package.

    The modules are found without importing them. A module with no
    ``.py`` source (an extension module, or a namespace package) is
    left out.

    Args:
        name: The name of the top-level package (or module).

    Returns:
        The source code of each module by dotted name, and the names of
        the modules that are packages.

    Raises:
        ModuleNotFoundError: If ``name`` cannot be found.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._graph import read_sources
    >>> sources, packages = read_sources("invoke_tasklib")
    >>> "invoke_tasklib._graph" in sources
    True
    >>> "invoke_tasklib" in packages
    True

    ```
    """
    spec = find_spec(name)
    if spec is None:
        msg = f"No module named '{name}'"
        raise ModuleNotFoundError(msg, name=name)
    roots = [Path(p) for p in spec.submodule_search_locations or []]
    sources: dict[str, str] = {}
    packages: set[str] = set()
    for module in discover_modules(name):
        path = _source_path(module, name, roots, spec.origin)
        if path is not None:
            sources[module] = path.read_text(encoding="utf-8")
            if path.name == "__init__.py":
                packages.add(module)
    return sources, packages


def _source_path(module: str, top: str, roots: list[Path], origin: str | None) -> Path | None:
    r"""Find the source file of a module of a package.

    Args:
        module: The dotted name of the module.
        top: The name of the checked package, dotted if it is in a
            namespace package (``"company.package"``).
        roots: The directories of that package.
        origin: The file of the top-level module, if it is not a
            package.

    Returns:
        The ``.py`` file of the module (the ``__init__.py`` of a
        package), or ``None`` if there is none.

    Example usage:

    ```pycon
    >>> from pathlib import Path
    >>> from invoke_tasklib._graph import _source_path
    >>> roots = [Path("/no/such/dir")]
    >>> _source_path("pkg.a", "pkg", roots, None) is None
    True

    ```
    """
    relative = Path(*module.removeprefix(top).lstrip(".").split("."))
    if module == top and not roots:
        return Path(origin) if origin and origin.endswith(".py") else None
    for root in roots:
        candidates = [root / relative / "__init__.py"]
        if module != top:
            candidates.append(root / relative.with_suffix(".py"))
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    return None
