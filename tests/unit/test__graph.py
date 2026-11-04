from __future__ import annotations

import ast
import importlib.machinery
import sys
from pathlib import Path

import pytest

from invoke_tasklib._graph import (
    _components,
    _cycle_in,
    _is_type_checking,
    _resolve,
    _source_path,
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
