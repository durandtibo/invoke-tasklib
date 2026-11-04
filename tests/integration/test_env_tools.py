from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

from invoke_tasklib import env

if TYPE_CHECKING:
    from pathlib import Path

TASKS = """
from invoke_tasklib import make_ns

ns = make_ns()
"""


def _check_tools(project: Path, path: str) -> subprocess.CompletedProcess[str]:
    (project / "tasks.py").write_text(TASKS)
    return subprocess.run(
        [sys.executable, "-m", "invoke", "env.check-tools"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PATH": path},
    )


def testfind_tool_finds_a_real_program() -> None:
    assert env.find_tool("python3" if os.name != "nt" else "python") is not None


def testfind_tool_finds_a_real_module() -> None:
    assert env.find_tool("invoke", module=True) is not None


def testfind_tool_does_not_find_a_missing_program() -> None:
    assert env.find_tool("no-such-program-xyz") is None


def testfind_tool_does_not_find_a_missing_module() -> None:
    assert env.find_tool("no_such_module_xyz", module=True) is None


def test_check_tools_reports_the_missing_tools_without_a_config(tmp_path: Path) -> None:
    proc = _check_tools(tmp_path, "/nonexistent")
    assert "❌ ruff: program not found." in proc.stdout


def test_check_tools_exits_with_code_127_when_a_tool_is_missing(tmp_path: Path) -> None:
    assert _check_tools(tmp_path, "/nonexistent").returncode == 127


def test_check_tools_names_the_missing_tools_in_the_error(tmp_path: Path) -> None:
    assert "tool(s) missing: uv, uvx, git, ruff" in _check_tools(tmp_path, "/nonexistent").stderr


def test_check_tools_finds_the_python_modules_of_the_interpreter(tmp_path: Path) -> None:
    proc = _check_tools(tmp_path, "/nonexistent")
    assert "✅ pytest: " in proc.stdout
