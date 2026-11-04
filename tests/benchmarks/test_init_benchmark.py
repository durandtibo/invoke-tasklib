from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

from invoke_tasklib import make_ns

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def _import_in_a_new_interpreter() -> int:
    r"""Import the package in a new interpreter, the start-up cost of
    every project that uses the library."""
    return subprocess.run([sys.executable, "-c", "import invoke_tasklib"], check=False).returncode


def test_make_ns(benchmark: BenchmarkFixture) -> None:
    assert len(benchmark(make_ns).collections) > 0


def test_import_in_a_new_interpreter(benchmark: BenchmarkFixture) -> None:
    assert benchmark.pedantic(_import_in_a_new_interpreter, rounds=5) == 0
