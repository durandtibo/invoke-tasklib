from __future__ import annotations

import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not installed")

TASKS = """
from invoke_tasklib import make_ns

ns = make_ns()
"""

PYPROJECT = """
[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/demo"]
"""


def _project(path: Path) -> None:
    (path / "src" / "demo").mkdir(parents=True)
    (path / "src" / "demo" / "__init__.py").write_text("")
    (path / "pyproject.toml").write_text(PYPROJECT)
    (path / "tasks.py").write_text(TASKS)
    (path / "invoke.yaml").write_text(
        "tasklib:\n  package:\n    name: demo\n  groups:\n    install: ''\n"
    )


def test_install_without_lock_file_resolves_and_creates_it(tmp_path: Path) -> None:
    _project(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "invoke", "env.install", "--no-optional-deps"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "uv.lock").is_file()
