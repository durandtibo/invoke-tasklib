from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from invoke_tasklib._files import find_files
from invoke_tasklib.formatting import SHELL_EXCLUDED_DIRS

if TYPE_CHECKING:
    from pathlib import Path

################################################
#     Tests for the shell script discovery     #
################################################


def _find_scripts(root: Path) -> list[str]:
    return [p.relative_to(root).as_posix() for p in find_files(root, ".sh", SHELL_EXCLUDED_DIRS)]


def test_find_sh_finds_scripts_of_the_project(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "run.sh").write_text("")
    (tmp_path / "top.sh").write_text("")
    assert _find_scripts(tmp_path) == ["src/run.sh", "top.sh"]


@pytest.mark.parametrize(
    "excluded", [".venv", ".git", "node_modules", "build", "dist", "site", ".pytest_cache"]
)
def test_find_sh_skips_excluded_dirs(tmp_path: Path, excluded: str) -> None:
    script_dir = tmp_path / excluded / "lib" / "bash"
    script_dir.mkdir(parents=True)
    (script_dir / "activate.sh").write_text("")
    assert _find_scripts(tmp_path) == []


def test_find_sh_keeps_scripts_next_to_excluded_dirs(tmp_path: Path) -> None:
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "activate.sh").write_text("")
    (tmp_path / "run.sh").write_text("")
    assert _find_scripts(tmp_path) == ["run.sh"]
