from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from invoke_tasklib.runner import build_command

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


@pytest.mark.parametrize("count", [100, 10_000])
def test_build_command_with_many_paths(benchmark: BenchmarkFixture, count: int) -> None:
    paths = " ".join(f"src/pkg/module_{i}.py" for i in range(count))
    command = benchmark(build_command, "ruff check", paths=paths)
    assert command.count(" ") == count + 1
