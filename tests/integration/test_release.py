from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest
from invoke.config import Config
from invoke.exceptions import Exit

from invoke_tasklib import release
from tests.integration.test_imports import _SubprocessContext

if TYPE_CHECKING:
    from pathlib import Path


def _git(*args: str) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],  # noqa: S607
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "1.2.3"\n')
    _git("init", "-q")
    _git("add", ".")
    _git("commit", "-q", "-m", "init")
    return tmp_path


def _context() -> _SubprocessContext:
    return _SubprocessContext(config=Config())


@pytest.mark.usefixtures("repo")
def test_check_release_state_accepts_a_tagged_clean_repository() -> None:
    _git("tag", "v1.2.3")
    assert release._check_release_state(_context()) is None


@pytest.mark.usefixtures("repo")
def test_check_release_state_rejects_an_untagged_repository() -> None:
    with pytest.raises(Exit, match=r"HEAD is not tagged"):
        release._check_release_state(_context())


def test_check_release_state_rejects_a_dirty_repository(repo: Path) -> None:
    _git("tag", "v1.2.3")
    (repo / "new.py").write_text("")
    with pytest.raises(Exit, match=r"working tree is not clean"):
        release._check_release_state(_context())


@pytest.mark.usefixtures("repo")
def test_check_release_state_rejects_a_wrong_tag() -> None:
    _git("tag", "v9.9.9")
    with pytest.raises(Exit, match=r"tag v9\.9\.9 does not match the version 1\.2\.3"):
        release._check_release_state(_context())
