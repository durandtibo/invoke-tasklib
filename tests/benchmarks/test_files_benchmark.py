from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from invoke_tasklib._files import find_files

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_benchmark.fixture import BenchmarkFixture


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    r"""A tree of 100 directories with 5 files each, 2 of them ``.sh``,
    and an excluded directory."""
    for i in range(100):
        directory = tmp_path / f"d{i}"
        directory.mkdir()
        for j in range(5):
            (directory / f"f{j}.{'sh' if j < 2 else 'py'}").write_text("")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "activate.sh").write_text("")
    return tmp_path


def test_find_files_in_a_tree(benchmark: BenchmarkFixture, tree: Path) -> None:
    assert len(benchmark(find_files, tree, ".sh")) == 200
