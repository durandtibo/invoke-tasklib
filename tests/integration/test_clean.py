from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from invoke.config import Config

from invoke_tasklib import clean
from tests.integration.test_imports import _SubprocessContext
from tests.integration.test_release import _git

if TYPE_CHECKING:
    from pathlib import Path


def _context() -> _SubprocessContext:
    return _SubprocessContext(config=Config())


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "script.sh").write_text("echo hi\n")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "pkg.whl").write_text("")
    _git("init", "-q")
    _git("add", "build")
    _git("commit", "-q", "-m", "init")
    return tmp_path


def test_all_keeps_a_build_directory_tracked_by_git(repo: Path) -> None:
    clean.all_(_context())
    assert (repo / "build" / "script.sh").is_file()


def test_all_removes_an_untracked_dist_directory(repo: Path) -> None:
    clean.all_(_context())
    assert not (repo / "dist").exists()


def test_all_dry_run_removes_nothing(repo: Path) -> None:
    clean.all_(_context(), dry_run=True)
    assert (repo / "dist" / "pkg.whl").is_file()


def test_all_outside_a_git_repository_removes_the_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "build").mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    clean.all_(_context())
    assert not (tmp_path / "build").exists()


def test_all_keeps_a_site_dir_outside_the_repository(repo: Path) -> None:
    outside = repo.parent / "shared-site"
    outside.mkdir()
    (repo / "mkdocs.yml").write_text(f"site_dir: {outside}\n")
    clean.all_(_context())
    assert outside.is_dir()


def test_all_removes_an_untracked_configured_coverage_html_dir(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[tool.coverage.html]\ndirectory = "reports/html"\n')
    (repo / "reports" / "html").mkdir(parents=True)
    clean.all_(_context())
    assert not (repo / "reports" / "html").exists()
