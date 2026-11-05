from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from invoke_tasklib._graph import find_cycles, import_graph

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def _imports(module: int) -> list[int]:
    r"""Return three modules below ``module``, spread by an arithmetic
    rule (the same on every run, so the benchmarks are comparable)."""
    return [(module * 31 + k * 17 + 7) % module for k in range(3)]


def _random_graph(size: int) -> dict[str, set[str]]:
    r"""Build a graph of ``size`` modules in which each module imports
    three lower-numbered ones, so the graph has no cycle."""
    return {f"m{i}": {f"m{j}" for j in _imports(i)} if i else set() for i in range(size)}


def _sources(size: int) -> dict[str, str]:
    r"""Build the sources of ``size`` modules that import three lower-
    numbered ones."""
    return {
        f"pkg.m{i}": "".join(f"import pkg.m{j}\n" for j in _imports(i)) if i else ""
        for i in range(size)
    }


@pytest.mark.parametrize("size", [1_000, 10_000])
def test_find_cycles_of_a_graph_without_cycle(benchmark: BenchmarkFixture, size: int) -> None:
    graph = _random_graph(size)
    assert benchmark(find_cycles, graph) == []


@pytest.mark.parametrize("size", [1_000, 10_000])
def test_find_cycles_of_a_graph_with_one_big_cycle(benchmark: BenchmarkFixture, size: int) -> None:
    graph = _random_graph(size)
    graph["m0"] = {f"m{size - 1}"}
    assert len(benchmark(find_cycles, graph)) >= 1


@pytest.mark.parametrize("size", [1_000, 5_000])
def test_import_graph_of_a_package(benchmark: BenchmarkFixture, size: int) -> None:
    sources = _sources(size)
    graph = benchmark(import_graph, sources)
    assert len(graph) == size
