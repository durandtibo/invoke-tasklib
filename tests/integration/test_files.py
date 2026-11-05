from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from invoke_tasklib import formatting, testing
from invoke_tasklib._files import project_files
from tests.integration.helpers import subprocess_context
from tests.integration.test_release import _git


def _touch(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")


def _found(suffix: str = ".sh") -> list[str]:
    return [path.as_posix() for path in project_files(subprocess_context(), Path(), suffix)]


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{name}_NAME", "Tester")
        monkeypatch.setenv(f"GIT_{name}_EMAIL", "tester@example.com")
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.chdir(tmp_path)
    _git("init", "-q")
    return tmp_path


def test_project_files_lists_the_tracked_files(repo: Path) -> None:
    _touch(repo, "a.sh", "src/b.sh")
    _git("add", "-A")
    assert _found() == ["a.sh", "src/b.sh"]


def test_project_files_lists_an_untracked_file(repo: Path) -> None:
    _touch(repo, "new.sh")
    assert _found() == ["new.sh"]


def test_project_files_follows_the_gitignore(repo: Path) -> None:
    (repo / ".gitignore").write_text("generated/\n*.tmp.sh\n")
    _touch(repo, "a.sh", "generated/b.sh", "c.tmp.sh")
    assert _found() == ["a.sh"]


def test_project_files_skips_a_virtual_environment_that_is_ignored(repo: Path) -> None:
    (repo / ".gitignore").write_text("venv/\n")
    _touch(repo, "a.sh", "venv/bin/activate.sh")
    assert _found() == ["a.sh"]


def test_project_files_keeps_a_file_in_a_directory_named_like_a_build_directory(
    repo: Path,
) -> None:
    _touch(repo, "src/pkg/site/run.sh", "src/pkg/build/make.sh")
    assert _found() == ["src/pkg/build/make.sh", "src/pkg/site/run.sh"]


def test_project_files_keeps_a_tracked_file_of_a_build_directory(repo: Path) -> None:
    _touch(repo, "build/tool.sh")
    _git("add", "-A")
    assert _found() == ["build/tool.sh"]


def test_project_files_leaves_out_a_deleted_tracked_file(repo: Path) -> None:
    _touch(repo, "a.sh", "b.sh")
    _git("add", "-A")
    (repo / "b.sh").unlink()
    assert _found() == ["a.sh"]


def test_project_files_leaves_out_an_unignored_environment(repo: Path) -> None:
    _touch(repo, "a.sh", ".venv/bin/activate.sh")
    assert _found() == ["a.sh"]


def test_project_files_keeps_a_name_with_a_space(repo: Path) -> None:
    _touch(repo, "my dir/a b.sh")
    assert _found() == ["my dir/a b.sh"]


def test_project_files_keeps_a_non_ascii_name(repo: Path) -> None:
    _touch(repo, "café/é.sh")
    assert _found() == ["café/é.sh"]


def test_project_files_filters_by_suffix(repo: Path) -> None:
    _touch(repo, "a.sh", "b.md", "c.shx")
    assert _found(".md") == ["b.md"]


def test_project_files_limits_the_search_to_a_directory(repo: Path) -> None:
    _touch(repo, "scripts/a.sh", "other/b.sh")
    found = project_files(subprocess_context(), Path("scripts"), ".sh")
    assert [path.as_posix() for path in found] == ["scripts/a.sh"]


def test_project_files_in_a_subdirectory_of_the_work_tree(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _touch(repo, "sub/a.sh", "b.sh")
    monkeypatch.chdir(repo / "sub")
    assert _found() == ["a.sh"]


def test_project_files_walks_outside_a_git_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _touch(tmp_path, "a.sh", ".venv/b.sh")
    monkeypatch.chdir(tmp_path)
    assert _found() == ["a.sh"]


def test_shell_tasks_skip_an_ignored_environment_with_any_name(repo: Path) -> None:
    (repo / ".gitignore").write_text("myenv/\n")
    _touch(repo, "run.sh", "myenv/bin/activate.sh")
    command = formatting._shell_command(subprocess_context(), "shellcheck", None, None)
    assert command == "shellcheck -- run.sh"


def test_markdown_doctests_keep_a_package_named_site(repo: Path) -> None:
    _touch(repo, "src/pkg/site/README.md", "README.md")
    found = testing._find_markdown_files(subprocess_context(), Path())
    assert [path.as_posix() for path in found] == ["README.md", "src/pkg/site/README.md"]
