from __future__ import annotations

import ast
import importlib.machinery
import itertools
import sys
from pathlib import Path

import pytest

from invoke_tasklib._graph import (
    _components,
    _cycle_in,
    _is_type_checking,
    _resolve,
    _source_path,
    _Tarjan,
    find_cycles,
    import_graph,
    parse_imports,
    read_sources,
)

#######################################
#     Tests for _is_type_checking     #
#######################################


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("TYPE_CHECKING", True),
        ("typing.TYPE_CHECKING", True),
        ("t.TYPE_CHECKING", True),
        ("DEBUG", False),
        ("a.DEBUG", False),
        ("not TYPE_CHECKING", False),
        ("True", False),
    ],
)
def test_is_type_checking(code: str, expected: bool) -> None:
    assert _is_type_checking(ast.parse(code, mode="eval").body) is expected


###################################
#     Tests for parse_imports     #
###################################


def test_parse_imports_import() -> None:
    assert parse_imports("import a.b, c", "pkg.m") == [("a.b", ()), ("c", ())]


def test_parse_imports_from_import() -> None:
    assert parse_imports("from a.b import c, d", "pkg.m") == [("a.b", ("c", "d"))]


def test_parse_imports_keeps_the_order_of_the_source() -> None:
    assert parse_imports("import b\nimport a\n", "pkg.m") == [("b", ()), ("a", ())]


def test_parse_imports_without_import_is_empty() -> None:
    assert parse_imports("x = 1\n", "pkg.m") == []


def test_parse_imports_relative_in_a_module() -> None:
    assert parse_imports("from . import b", "pkg.sub.m") == [("pkg.sub", ("b",))]


def test_parse_imports_relative_in_a_package() -> None:
    assert parse_imports("from . import b", "pkg.sub", is_package=True) == [("pkg.sub", ("b",))]


def test_parse_imports_relative_two_levels_up() -> None:
    assert parse_imports("from ..x import y", "pkg.sub.m") == [("pkg.x", ("y",))]


def test_parse_imports_relative_with_a_module() -> None:
    assert parse_imports("from .b import y", "pkg.m") == [("pkg.b", ("y",))]


def test_parse_imports_relative_import_in_a_top_level_module_is_rejected() -> None:
    with pytest.raises(SyntaxError, match=r"attempted relative import beyond top-level package"):
        parse_imports("from . import b", "m")


def test_parse_imports_relative_import_above_the_top_level_package_is_rejected() -> None:
    with pytest.raises(SyntaxError, match=r"attempted relative import beyond top-level package"):
        parse_imports("from ... import x", "pkg.a")


def test_parse_imports_relative_import_to_the_top_level_package_is_accepted() -> None:
    assert parse_imports("from .. import x", "pkg.sub.a") == [("pkg", ("x",))]


def test_parse_imports_relative_import_above_a_package_is_rejected() -> None:
    with pytest.raises(SyntaxError, match=r"attempted relative import beyond top-level package"):
        parse_imports("from .. import x", "pkg", is_package=True)


def test_parse_imports_relative_error_names_the_module() -> None:
    with pytest.raises(SyntaxError, match=r"beyond top-level") as info:
        parse_imports("from ... import x", "pkg.a")
    assert info.value.filename == "pkg.a"


def test_parse_imports_relative_error_has_the_line_of_the_import() -> None:
    with pytest.raises(SyntaxError, match=r"beyond top-level") as info:
        parse_imports("import os\nfrom ... import x", "pkg.a")
    assert info.value.lineno == 2


def test_parse_imports_ignores_type_checking_by_default() -> None:
    source = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import a\n"
    assert parse_imports(source, "pkg.m") == [("typing", ("TYPE_CHECKING",))]


def test_parse_imports_can_include_type_checking() -> None:
    source = "if TYPE_CHECKING:\n    import a\n"
    assert parse_imports(source, "pkg.m", type_checking=True) == [("a", ())]


def test_parse_imports_keeps_the_else_of_type_checking() -> None:
    source = "if TYPE_CHECKING:\n    import a\nelse:\n    import b\n"
    assert parse_imports(source, "pkg.m") == [("b", ())]


def test_parse_imports_keeps_the_imports_of_other_conditions() -> None:
    assert parse_imports("if DEBUG:\n    import a\n", "pkg.m") == [("a", ())]


def test_parse_imports_keeps_the_imports_of_a_try() -> None:
    source = "try:\n    import a\nexcept ImportError:\n    import b\n"
    assert parse_imports(source, "pkg.m") == [("a", ()), ("b", ())]


def test_parse_imports_keeps_the_imports_of_a_class_body() -> None:
    assert parse_imports("class A:\n    import a\n", "pkg.m") == [("a", ())]


@pytest.mark.parametrize(
    "source",
    [
        "def f():\n    import a\n",
        "async def f():\n    import a\n",
        "f = lambda: __import__('a')\n",
    ],
)
def test_parse_imports_ignores_functions_by_default(source: str) -> None:
    assert parse_imports(source, "pkg.m") == []


@pytest.mark.parametrize("source", ["def f():\n    import a\n", "async def f():\n    import a\n"])
def test_parse_imports_can_include_functions(source: str) -> None:
    assert parse_imports(source, "pkg.m", lazy=True) == [("a", ())]


def test_parse_imports_lazy_includes_a_method() -> None:
    source = "class A:\n    def f(self):\n        from b import c\n"
    assert parse_imports(source, "pkg.m", lazy=True) == [("b", ("c",))]


def test_parse_imports_lazy_visits_a_lambda_body() -> None:
    assert parse_imports("f = lambda: 1\n", "pkg.m", lazy=True) == []


def test_parse_imports_rejects_invalid_source() -> None:
    with pytest.raises(SyntaxError, match=r"invalid syntax"):
        parse_imports("def (:\n", "pkg.m")


##############################
#     Tests for _resolve     #
##############################


def test_resolve_exact_module() -> None:
    assert _resolve("pkg.a", {"pkg", "pkg.a"}) == "pkg.a"


def test_resolve_longest_known_prefix() -> None:
    assert _resolve("pkg.a.X.y", {"pkg", "pkg.a"}) == "pkg.a"


def test_resolve_unknown_is_none() -> None:
    assert _resolve("os.path", {"pkg"}) is None


def test_resolve_does_not_match_a_partial_name() -> None:
    assert _resolve("pkgx.a", {"pkg"}) is None


##################################
#     Tests for import_graph     #
##################################


def test_import_graph_whole_output() -> None:
    sources = {
        "p": "from p import a",
        "p.a": "import p.b\nimport os",
        "p.b": "from . import a",
        "p.c": "",
    }
    assert import_graph(sources, ["p"]) == {
        "p": {"p.a"},
        "p.a": {"p.b"},
        "p.b": {"p.a"},
        "p.c": set(),
    }


def test_import_graph_from_import_of_a_module_is_an_edge_to_the_module() -> None:
    sources = {"p": "", "p.a": "from p import b", "p.b": ""}
    assert import_graph(sources, ["p"])["p.a"] == {"p.b"}


def test_import_graph_from_import_of_an_attribute_is_an_edge_to_the_package() -> None:
    sources = {"p": "X = 1", "p.a": "from p import X"}
    assert import_graph(sources, ["p"])["p.a"] == {"p"}


def test_import_graph_import_of_a_submodule_is_an_edge_to_it() -> None:
    sources = {"p": "", "p.a": "import p.b.c", "p.b": "", "p.b.c": ""}
    assert import_graph(sources, ["p", "p.b"])["p.a"] == {"p.b.c"}


def test_import_graph_ignores_external_imports() -> None:
    assert import_graph({"p": "import os\nfrom sys import path"}, ["p"]) == {"p": set()}


def test_import_graph_ignores_a_self_import() -> None:
    assert import_graph({"p.a": "import p.a"}) == {"p.a": set()}


def test_import_graph_resolves_relative_imports_of_a_package() -> None:
    sources = {"p": "", "p.s": "from . import m", "p.s.m": ""}
    assert import_graph(sources, ["p", "p.s"])["p.s"] == {"p.s.m"}


def test_import_graph_resolves_relative_imports_of_a_module() -> None:
    sources = {"p": "", "p.s": "", "p.s.m": "from . import n", "p.s.n": ""}
    assert import_graph(sources, ["p", "p.s"])["p.s.m"] == {"p.s.n"}


def test_import_graph_ignores_lazy_imports_by_default() -> None:
    sources = {"p.a": "def f():\n    import p.b\n", "p.b": ""}
    assert import_graph(sources)["p.a"] == set()


def test_import_graph_can_follow_lazy_imports() -> None:
    sources = {"p.a": "def f():\n    import p.b\n", "p.b": ""}
    assert import_graph(sources, lazy=True)["p.a"] == {"p.b"}


def test_import_graph_can_follow_type_checking_imports() -> None:
    sources = {"p.a": "if TYPE_CHECKING:\n    import p.b\n", "p.b": ""}
    assert import_graph(sources, type_checking=True)["p.a"] == {"p.b"}


def test_import_graph_does_not_mutate_its_inputs() -> None:
    sources = {"p.a": "import p.b", "p.b": ""}
    packages = ["p"]
    import_graph(sources, packages)
    assert (sources, packages) == ({"p.a": "import p.b", "p.b": ""}, ["p"])


def test_import_graph_is_deterministic() -> None:
    sources = {"p.a": "import p.b", "p.b": "import p.a"}
    assert import_graph(sources) == import_graph(sources)


def test_import_graph_of_nothing_is_empty() -> None:
    assert import_graph({}) == {}


def test_import_graph_rejects_invalid_source() -> None:
    with pytest.raises(SyntaxError, match=r"invalid syntax"):
        import_graph({"p.a": "def (:\n"})


#############################
#     Tests for _Tarjan     #
#############################


def _tarjan_with_stack(stack: list[str]) -> _Tarjan:
    tarjan = _Tarjan({})
    tarjan.stack = list(stack)
    tarjan.on_stack = set(stack)
    return tarjan


def test_tarjan_push_puts_the_node_on_the_stack() -> None:
    tarjan = _Tarjan({"a": []})
    tarjan._push("a")
    assert tarjan.stack == ["a"]


def test_tarjan_push_marks_the_node_as_on_the_stack() -> None:
    tarjan = _Tarjan({"a": []})
    tarjan._push("a")
    assert tarjan.on_stack == {"a"}


def test_tarjan_push_returns_the_sorted_children() -> None:
    node, children = _Tarjan({"a": ["c", "b"], "b": [], "c": []})._push("a")
    assert (node, list(children)) == ("a", ["b", "c"])


def test_tarjan_pop_component_removes_only_the_nodes_above_the_root() -> None:
    tarjan = _tarjan_with_stack(["a", "b", "c"])
    tarjan._pop_component("b")
    assert tarjan.stack == ["a"]


def test_tarjan_pop_component_unmarks_the_popped_nodes() -> None:
    tarjan = _tarjan_with_stack(["a", "b", "c"])
    tarjan._pop_component("b")
    assert tarjan.on_stack == {"a"}


def test_tarjan_pop_component_keeps_a_cycle() -> None:
    tarjan = _tarjan_with_stack(["a", "b", "c"])
    tarjan._pop_component("b")
    assert tarjan.found == [["b", "c"]]


def test_tarjan_pop_component_drops_a_single_node() -> None:
    tarjan = _tarjan_with_stack(["a", "b"])
    tarjan._pop_component("b")
    assert tarjan.found == []


def test_tarjan_pop_component_of_the_only_node_empties_the_stack() -> None:
    tarjan = _tarjan_with_stack(["a"])
    tarjan._pop_component("a")
    assert (tarjan.stack, tarjan.on_stack) == ([], set())


def test_tarjan_run_leaves_nothing_on_the_stack() -> None:
    tarjan = _Tarjan({"a": ["b"], "b": ["a", "c"], "c": []})
    tarjan.run()
    assert (tarjan.stack, tarjan.on_stack) == ([], set())


def test_tarjan_run_ignores_an_edge_to_a_finished_component() -> None:
    graph = {"a": ["b"], "b": ["a"], "c": ["a"], "d": ["c"]}
    assert _Tarjan(graph).run() == [["a", "b"]]


def test_tarjan_run_is_deterministic() -> None:
    graph = {"a": ["b"], "b": ["c"], "c": ["a"], "d": ["a"]}
    assert _Tarjan(graph).run() == _Tarjan(graph).run()


#################################
#     Tests for _components     #
#################################


def test_components_of_an_acyclic_graph_is_empty() -> None:
    assert _components({"a": ["b"], "b": ["c"], "c": []}) == []


def test_components_of_an_empty_graph_is_empty() -> None:
    assert _components({}) == []


def test_components_ignores_a_single_node() -> None:
    assert _components({"a": []}) == []


def test_components_finds_a_two_node_cycle() -> None:
    assert _components({"a": ["b"], "b": ["a"]}) == [["a", "b"]]


def test_components_excludes_the_nodes_around_a_cycle() -> None:
    assert _components({"a": ["b"], "b": ["a", "c"], "c": [], "d": ["a"]}) == [["a", "b"]]


def test_components_finds_two_separate_cycles() -> None:
    graph = {"a": ["b"], "b": ["a"], "c": ["d"], "d": ["c"]}
    assert _components(graph) == [["a", "b"], ["c", "d"]]


def test_components_merges_overlapping_cycles() -> None:
    graph = {"a": ["b"], "b": ["c", "a"], "c": ["a"]}
    assert _components(graph) == [["a", "b", "c"]]


def test_components_handles_a_long_chain_without_recursion() -> None:
    n = 3000
    graph = {str(i): [str(i + 1)] for i in range(n)}
    graph[str(n)] = ["0"]
    assert len(_components(graph)[0]) == n + 1


###############################
#     Tests for _cycle_in     #
###############################


def test_cycle_in_finds_the_shortest_cycle() -> None:
    graph = {"a": ["b", "c"], "b": ["c"], "c": ["a"]}
    assert _cycle_in(["a", "b", "c"], graph) == ["a", "c", "a"]


def test_cycle_in_starts_and_ends_on_the_first_node() -> None:
    graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
    assert _cycle_in(["a", "b", "c"], graph) == ["a", "b", "c", "a"]


def test_cycle_in_rejects_a_component_that_is_not_cyclic() -> None:
    with pytest.raises(ValueError, match=r"No cycle goes through 'a'"):
        _cycle_in(["a", "b"], {"a": ["b"], "b": []})


#################################
#     Tests for find_cycles     #
#################################


def test_find_cycles_none() -> None:
    assert find_cycles({"a": ["b"], "b": []}) == []


def test_find_cycles_one_per_component() -> None:
    assert find_cycles({"a": ["b"], "b": ["c"], "c": ["a", "b"]}) == [["a", "b", "c", "a"]]


def test_find_cycles_whole_output() -> None:
    graph = {"a": ["b"], "b": ["a"], "c": ["d"], "d": ["c"], "e": ["a"]}
    assert find_cycles(graph) == [["a", "b", "a"], ["c", "d", "c"]]


def test_find_cycles_is_sorted_and_deterministic() -> None:
    graph = {"z": ["y"], "y": ["z"], "a": ["b"], "b": ["a"]}
    assert find_cycles(graph) == find_cycles(dict(reversed(graph.items())))


def _random_graph(seed: int) -> dict[str, list[str]]:
    r"""Create a small pseudo-random graph, with self-loops allowed.

    The numbers come from a linear congruential generator, so the graph
    only depends on the seed.

    Args:
        seed: The seed of the generator.

    Returns:
        The nodes that each node points to, for 2 to 7 nodes named
        ``n0``, ``n1``, ...
    """
    state = seed

    def draw(modulo: int) -> int:
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) % 2**64
        return (state >> 33) % modulo

    nodes = [f"n{i}" for i in range(2 + draw(6))]
    return {node: [t for t in nodes if draw(4) == 0] for node in nodes}


def _reachable(graph: dict[str, list[str]], start: str) -> set[str]:
    r"""Return the nodes reachable from a node by one edge or more.

    Args:
        graph: The nodes that each node points to.
        start: The node to start from.

    Returns:
        The reachable nodes. ``start`` is in it only if it is on a
        cycle.
    """
    seen: set[str] = set()
    todo = list(graph[start])
    while todo:
        node = todo.pop()
        if node not in seen:
            seen.add(node)
            todo.extend(graph[node])
    return seen


def _brute_force_components(graph: dict[str, list[str]]) -> set[frozenset[str]]:
    r"""Find the groups of at least two nodes that reach each other.

    Args:
        graph: The nodes that each node points to.

    Returns:
        The strongly connected components of two nodes or more, found
        from the reachability of every node.
    """
    reach = {node: _reachable(graph, node) for node in graph}
    components = {
        frozenset(m for m in graph if m == node or (m in reach[node] and node in reach[m]))
        for node in graph
        if node in reach[node]
    }
    return {component for component in components if len(component) > 1}


_RANDOM_GRAPHS = [_random_graph(seed) for seed in range(40)]


def _component_of(node: str, components: set[frozenset[str]]) -> list[str]:
    r"""Return the sorted nodes of the component that has a node.

    Args:
        node: The node to look for.
        components: The components.

    Returns:
        The sorted nodes of the first component that has ``node``.
    """
    return sorted(next(c for c in components if node in c))


@pytest.mark.parametrize("graph", _RANDOM_GRAPHS)
def test_find_cycles_reports_one_cycle_per_component_of_a_random_graph(
    graph: dict[str, list[str]],
) -> None:
    components = _brute_force_components(graph)
    assert sorted(_component_of(cycle[0], components) for cycle in find_cycles(graph)) == sorted(
        sorted(component) for component in components
    )


@pytest.mark.parametrize("graph", _RANDOM_GRAPHS)
def test_find_cycles_returns_closed_paths_of_a_random_graph(
    graph: dict[str, list[str]],
) -> None:
    cycles = find_cycles(graph)
    assert all(
        cycle[0] == cycle[-1] and all(b in graph[a] for a, b in itertools.pairwise(cycle))
        for cycle in cycles
    )


##################################
#     Tests for read_sources     #
##################################


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "graphpkg"
    (root / "sub").mkdir(parents=True)
    (root / "__init__.py").write_text("A = 1\n")
    (root / "a.py").write_text("import graphpkg.sub\n")
    (root / "sub" / "__init__.py").write_text("")
    (root / "sub" / "b.py").write_text("B = 2\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    return root


@pytest.mark.usefixtures("package")
def test_read_sources_whole_output() -> None:
    assert read_sources("graphpkg") == (
        {
            "graphpkg": "A = 1\n",
            "graphpkg.a": "import graphpkg.sub\n",
            "graphpkg.sub": "",
            "graphpkg.sub.b": "B = 2\n",
        },
        {"graphpkg", "graphpkg.sub"},
    )


@pytest.mark.usefixtures("package")
def test_read_sources_of_a_dotted_name() -> None:
    assert read_sources("graphpkg.sub") == (
        {"graphpkg.sub": "", "graphpkg.sub.b": "B = 2\n"},
        {"graphpkg.sub"},
    )


def test_read_sources_of_a_dotted_name_does_not_import_the_parent(package: Path) -> None:
    (package / "__init__.py").write_text("raise RuntimeError('imported')\n")
    assert read_sources("graphpkg.sub")[1] == {"graphpkg.sub"}


@pytest.mark.usefixtures("package")
def test_read_sources_of_an_unknown_dotted_name() -> None:
    with pytest.raises(ModuleNotFoundError, match=r"No module named 'graphpkg\.nope'"):
        read_sources("graphpkg.nope")


def test_read_sources_leaves_out_an_extension_module(package: Path) -> None:
    (package / f"native{importlib.machinery.EXTENSION_SUFFIXES[0]}").write_text("")
    assert "graphpkg.native" not in read_sources("graphpkg")[0]


@pytest.mark.usefixtures("package")
def test_read_sources_does_not_import_the_package() -> None:
    read_sources("graphpkg")
    assert "graphpkg" not in sys.modules


def test_read_sources_of_a_single_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "graphsingle.py").write_text("X = 1\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    assert read_sources("graphsingle") == ({"graphsingle": "X = 1\n"}, set())


def test_read_sources_from_a_directory_whole_output(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "__init__.py").write_text("A = 1\n")
    (tmp_path / "a.py").write_text("import notinstalled.sub\n")
    (tmp_path / "sub" / "__init__.py").write_text("")
    assert read_sources("notinstalled", src=tmp_path) == (
        {
            "notinstalled": "A = 1\n",
            "notinstalled.a": "import notinstalled.sub\n",
            "notinstalled.sub": "",
        },
        {"notinstalled", "notinstalled.sub"},
    )


def test_read_sources_from_a_directory_does_not_need_the_package_to_be_installed(
    tmp_path: Path,
) -> None:
    (tmp_path / "__init__.py").write_text("")
    assert read_sources("no_such_graph_pkg", src=tmp_path)[1] == {"no_such_graph_pkg"}


@pytest.mark.usefixtures("package")
def test_read_sources_from_a_directory_wins_over_the_installed_copy(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    (other / "__init__.py").write_text("SOURCE = 1\n")
    assert read_sources("graphpkg", src=other)[0] == {"graphpkg": "SOURCE = 1\n"}


def test_read_sources_from_a_directory_without_init_leaves_the_package_out(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text("")
    assert read_sources("noinit", src=tmp_path)[0] == {"noinit.a": ""}


@pytest.mark.usefixtures("package")
def test_read_sources_falls_back_to_the_installed_copy_without_the_directory(
    tmp_path: Path,
) -> None:
    assert "graphpkg.a" in read_sources("graphpkg", src=tmp_path / "missing")[0]


def test_read_sources_with_a_missing_directory_and_package_raises(tmp_path: Path) -> None:
    with pytest.raises(ModuleNotFoundError, match=r"No module named 'no_such_graph_pkg'"):
        read_sources("no_such_graph_pkg", src=tmp_path / "missing")


def test_read_sources_of_a_missing_package() -> None:
    with pytest.raises(ModuleNotFoundError, match=r"No module named 'no_such_graph_pkg'"):
        read_sources("no_such_graph_pkg")


##################################
#     Tests for _source_path     #
##################################


def test_source_path_of_a_module(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("")
    assert _source_path("pkg.a", "pkg", [tmp_path], None) == tmp_path / "a.py"


def test_source_path_of_a_package(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "__init__.py").write_text("")
    assert _source_path("pkg.sub", "pkg", [tmp_path], None) == tmp_path / "sub" / "__init__.py"


def test_source_path_of_the_top_level_package(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text("")
    assert _source_path("pkg", "pkg", [tmp_path], None) == tmp_path / "__init__.py"


def test_source_path_of_a_top_level_module() -> None:
    assert _source_path("m", "m", [], "/x/m.py") == Path("/x/m.py")


def test_source_path_of_a_compiled_top_level_module() -> None:
    assert _source_path("m", "m", [], "/x/m.so") is None


def test_source_path_of_a_top_level_module_without_origin() -> None:
    assert _source_path("m", "m", [], None) is None


def test_source_path_of_a_missing_module(tmp_path: Path) -> None:
    assert _source_path("pkg.a", "pkg", [tmp_path], None) is None


def test_source_path_looks_in_every_root(tmp_path: Path) -> None:
    (tmp_path / "second").mkdir()
    (tmp_path / "second" / "a.py").write_text("")
    roots = [tmp_path / "first", tmp_path / "second"]
    assert _source_path("pkg.a", "pkg", roots, None) == tmp_path / "second" / "a.py"


def test_source_path_of_a_missing_module_in_every_root(tmp_path: Path) -> None:
    assert _source_path("pkg.a", "pkg", [tmp_path / "x", tmp_path / "y"], None) is None
