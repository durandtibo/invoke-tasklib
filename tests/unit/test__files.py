from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from invoke_tasklib._files import find_files

if TYPE_CHECKING:
    import pytest

################################
#     Tests for find_files     #
################################


def _touch(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")


def test_find_files_returns_sorted_paths(tmp_path: Path) -> None:
    _touch(tmp_path, "b.sh", "a.sh", "src/c.sh")
    assert find_files(tmp_path, ".sh") == [
        tmp_path / "a.sh",
        tmp_path / "b.sh",
        tmp_path / "src" / "c.sh",
    ]


def test_find_files_empty_directory(tmp_path: Path) -> None:
    assert find_files(tmp_path, ".sh") == []


def test_find_files_ignores_other_suffixes(tmp_path: Path) -> None:
    _touch(tmp_path, "a.sh", "b.py", "c.shx")
    assert find_files(tmp_path, ".sh") == [tmp_path / "a.sh"]


def test_find_files_does_not_walk_into_default_excluded_dirs(tmp_path: Path) -> None:
    _touch(tmp_path, ".venv/a.sh", "b.sh")
    assert find_files(tmp_path, ".sh") == [tmp_path / "b.sh"]


def test_find_files_skips_excluded_dirs_at_any_depth(tmp_path: Path) -> None:
    _touch(tmp_path, "pkg/.git/a.sh", "pkg/b.sh")
    assert find_files(tmp_path, ".sh") == [tmp_path / "pkg" / "b.sh"]


def test_find_files_uses_the_given_excluded_dirs(tmp_path: Path) -> None:
    _touch(tmp_path, "build/a.sh", ".venv/b.sh")
    assert find_files(tmp_path, ".sh", {"build"}) == [tmp_path / ".venv" / "b.sh"]


def test_find_files_without_excluded_dirs_walks_everything(tmp_path: Path) -> None:
    _touch(tmp_path, ".venv/a.sh")
    assert find_files(tmp_path, ".sh", ()) == [tmp_path / ".venv" / "a.sh"]


def test_find_files_current_directory_has_no_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _touch(tmp_path, "a.sh")
    monkeypatch.chdir(tmp_path)
    assert find_files(Path(), ".sh") == [Path("a.sh")]


def test_find_files_does_not_modify_the_excluded_set(tmp_path: Path) -> None:
    excluded = {"build"}
    find_files(tmp_path, ".sh", excluded)
    assert excluded == {"build"}
