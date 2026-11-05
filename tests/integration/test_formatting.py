from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest
from invoke.exceptions import UnexpectedExit

from invoke_tasklib import formatting
from invoke_tasklib._files import find_files
from tests.integration.helpers import subprocess_context

if TYPE_CHECKING:
    from pathlib import Path

################################################
#     Tests for the shell script discovery     #
################################################


def _find_scripts(root: Path) -> list[str]:
    return [p.relative_to(root).as_posix() for p in find_files(root, ".sh")]


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


#############################################
#     Tests for the shell format check     #
#############################################

UNFORMATTED = "if true; then\necho hi\nfi\n"
FORMATTED = "if true; then\n\techo hi\nfi\n"


@pytest.mark.skipif(shutil.which("shfmt") is None, reason="shfmt is not installed")
def test_check_shell_format_accepts_a_formatted_script(tmp_path: Path) -> None:
    script = tmp_path / "ok.sh"
    script.write_text(FORMATTED)
    assert formatting.check_shell_format(subprocess_context(), paths=str(script)) is None


@pytest.mark.skipif(shutil.which("shfmt") is None, reason="shfmt is not installed")
def test_check_shell_format_rejects_an_unformatted_script(tmp_path: Path) -> None:
    script = tmp_path / "bad.sh"
    script.write_text(UNFORMATTED)
    with pytest.raises(UnexpectedExit, match=r"bad command exit code"):
        formatting.check_shell_format(subprocess_context(), paths=str(script))


@pytest.mark.skipif(shutil.which("shfmt") is None, reason="shfmt is not installed")
def test_check_shell_format_does_not_modify_the_script(tmp_path: Path) -> None:
    script = tmp_path / "bad.sh"
    script.write_text(UNFORMATTED)
    with pytest.raises(UnexpectedExit, match=r"bad command exit code"):
        formatting.check_shell_format(subprocess_context(), paths=str(script))
    assert script.read_text() == UNFORMATTED


@pytest.mark.skipif(shutil.which("shfmt") is None, reason="shfmt is not installed")
def test_fix_shell_makes_the_script_pass_the_format_check(tmp_path: Path) -> None:
    script = tmp_path / "bad.sh"
    script.write_text(UNFORMATTED)
    formatting.fix_shell(subprocess_context(), paths=str(script))
    assert formatting.check_shell_format(subprocess_context(), paths=str(script)) is None
