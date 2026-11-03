from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import clean

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _context() -> MockContext:
    return MockContext(config=Config(), run=True)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _mkdir(*parts: str) -> Callable[[Path], Path]:
    def make(root: Path) -> Path:
        path = root.joinpath(*parts)
        path.mkdir(parents=True)
        return path

    return make


#########################
#     Tests for all     #
#########################


def test_all_removes_artifact_dirs(project: Path) -> None:
    _mkdir("dist")(project)
    _mkdir("htmlcov")(project)
    clean.all(_context())
    assert not (project / "dist").exists()
    assert not (project / "htmlcov").exists()


def test_all_removes_mypy_cache(project: Path) -> None:
    _mkdir(".mypy_cache")(project)
    clean.all(_context())
    assert not (project / ".mypy_cache").exists()


def test_all_removes_artifact_files(project: Path) -> None:
    (project / ".coverage").write_text("")
    (project / "coverage.xml").write_text("")
    clean.all(_context())
    assert [p.name for p in project.iterdir()] == []


def test_all_removes_egg_info(project: Path) -> None:
    _mkdir("pkg.egg-info")(project)
    clean.all(_context())
    assert not (project / "pkg.egg-info").exists()


def test_all_removes_nested_pycache(project: Path) -> None:
    _mkdir("src", "pkg", "__pycache__")(project)
    clean.all(_context())
    assert not (project / "src" / "pkg" / "__pycache__").exists()


def test_all_keeps_other_files(project: Path) -> None:
    (project / "README.md").write_text("")
    clean.all(_context())
    assert (project / "README.md").exists()


def test_all_does_not_touch_pycache_in_venv(project: Path) -> None:
    venv_cache = _mkdir(".venv", "lib", "__pycache__")(project)
    clean.all(_context())
    assert venv_cache.exists()


def test_all_does_not_touch_pycache_in_node_modules(project: Path) -> None:
    cache = _mkdir("node_modules", "pkg", "__pycache__")(project)
    clean.all(_context())
    assert cache.exists()


def test_all_no_artifacts_keeps_empty_project_unchanged(project: Path) -> None:
    clean.all(_context())
    assert list(project.iterdir()) == []


def test_all_reports_progress(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _mkdir("dist")(project)
    clean.all(_context())
    assert capsys.readouterr().out == (
        "🧹 Cleaning build artifacts and caches...\n🗑️  Removing dist\n✅ Cleanup complete\n"
    )


#############################
#     Tests for pycache     #
#############################


def test_pycache_removes_nested_pycache_dirs(project: Path) -> None:
    _mkdir("a", "b", "__pycache__")(project)
    _mkdir("__pycache__")(project)
    clean.pycache(_context())
    assert [p.name for p in project.rglob("__pycache__")] == []


def test_pycache_keeps_other_dirs(project: Path) -> None:
    _mkdir("dist")(project)
    clean.pycache(_context())
    assert (project / "dist").exists()


def test_pycache_does_not_touch_venv(project: Path) -> None:
    venv_cache = _mkdir(".venv", "lib", "__pycache__")(project)
    clean.pycache(_context())
    assert venv_cache.exists()


########################################
#     Tests for _find_pycache_dirs     #
########################################


def test_find_pycache_dirs_returns_sorted_paths(tmp_path: Path) -> None:
    _mkdir("b", "__pycache__")(tmp_path)
    _mkdir("a", "__pycache__")(tmp_path)
    assert clean._find_pycache_dirs(tmp_path) == [
        tmp_path / "a" / "__pycache__",
        tmp_path / "b" / "__pycache__",
    ]


def test_find_pycache_dirs_empty(tmp_path: Path) -> None:
    assert clean._find_pycache_dirs(tmp_path) == []


@pytest.mark.parametrize("excluded", [".venv", ".git", "node_modules", ".pytest_cache"])
def test_find_pycache_dirs_skips_excluded_dirs(tmp_path: Path, excluded: str) -> None:
    _mkdir(excluded, "pkg", "__pycache__")(tmp_path)
    assert clean._find_pycache_dirs(tmp_path) == []


def test_find_pycache_dirs_skips_excluded_dir_but_finds_sibling(tmp_path: Path) -> None:
    _mkdir(".venv", "__pycache__")(tmp_path)
    _mkdir("src", "__pycache__")(tmp_path)
    assert clean._find_pycache_dirs(tmp_path) == [tmp_path / "src" / "__pycache__"]


def test_find_pycache_dirs_does_not_descend_into_pycache(tmp_path: Path) -> None:
    _mkdir("__pycache__", "__pycache__")(tmp_path)
    assert clean._find_pycache_dirs(tmp_path) == [tmp_path / "__pycache__"]


#################################
#     Tests for _remove_dir     #
#################################


def test_remove_dir_removes_existing_dir(tmp_path: Path) -> None:
    target = _mkdir("cache")(tmp_path)
    clean._remove_dir(_context(), target)
    assert not target.exists()


def test_remove_dir_ignores_missing_dir(tmp_path: Path) -> None:
    clean._remove_dir(_context(), tmp_path / "missing")
    assert tmp_path.exists()


def test_remove_dir_reports_removal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = _mkdir("cache")(tmp_path)
    clean._remove_dir(_context(), target)
    assert capsys.readouterr().out == f"🗑️  Removing {target}\n"


##################################
#     Tests for _remove_file     #
##################################


def test_remove_file_removes_existing_file(tmp_path: Path) -> None:
    target = tmp_path / ".coverage"
    target.write_text("data")
    clean._remove_file(_context(), target)
    assert not target.exists()


def test_remove_file_ignores_missing_file(tmp_path: Path) -> None:
    clean._remove_file(_context(), tmp_path / "missing")
    assert tmp_path.exists()
