from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import clean

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def _context() -> MockContext:
    return MockContext(config=Config(), run=True)


def test_all_removes_existing_dirs_and_files(monkeypatch: MonkeyPatch) -> None:
    removed_dirs: list[Path] = []
    removed_files: list[Path] = []

    monkeypatch.setattr(Path, "is_dir", lambda _self: str(_self) in {"dist", "htmlcov"})
    monkeypatch.setattr(Path, "is_file", lambda _self: str(_self) == ".coverage")
    monkeypatch.setattr(Path, "glob", lambda _self, _pattern: iter([]))
    monkeypatch.setattr("shutil.rmtree", lambda p: removed_dirs.append(p))
    monkeypatch.setattr(Path, "unlink", lambda _self: removed_files.append(_self))

    c = _context()
    clean.all(c)

    assert {str(p) for p in removed_dirs} == {"dist", "htmlcov"}
    assert {str(p) for p in removed_files} == {".coverage"}


def test_all_no_artifacts(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "is_dir", lambda _self: False)
    monkeypatch.setattr(Path, "is_file", lambda _self: False)
    monkeypatch.setattr(Path, "glob", lambda _self, _pattern: iter([]))

    c = _context()
    clean.all(c)
