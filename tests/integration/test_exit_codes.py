from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src"
TASKS = "from invoke_tasklib import make_ns\n\nns = make_ns()\n"
VALID_YAML = 'tasklib:\n  package:\n    name: demo\n    python_version: "3.10"\n'
INVALID_YAML = "tasklib:\n  nope: 1\n"


def _inv(project: Path, *args: str, path: str | None = None) -> subprocess.CompletedProcess[str]:
    r"""Run ``inv`` in ``project`` with the real Invoke runner.

    Args:
        project: The working directory.
        *args: The arguments of ``inv``.
        path: The ``PATH`` of the process. By default it starts with
            the directory of the running interpreter, so the tools of
            the virtual environment are found.

    Returns:
        The completed process.
    """
    if path is None:
        path = f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}"
    env = {**os.environ, "PYTHONPATH": str(SRC), "PATH": path}
    return subprocess.run(  # noqa: S603 (fixed command)
        [sys.executable, "-m", "invoke", *args],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _project(root: Path, yaml: str, module: str) -> Path:
    r"""Create a project with a config, a module and a shell script."""
    (root / "tasks.py").write_text(TASKS)
    (root / "invoke.yaml").write_text(yaml)
    (root / "demo.py").write_text(module)
    (root / "run.sh").write_text("#!/bin/sh\necho ok\n")
    return root


def _bash_only(root: Path) -> str:
    r"""Create a ``PATH`` directory with ``bash`` and no other tool."""
    bin_dir = root / "bin"
    bin_dir.mkdir()
    (bin_dir / "bash").symlink_to(shutil.which("bash") or "/bin/bash")
    return str(bin_dir)


#################################
#     Tests for the exit codes  #
#################################


@pytest.mark.parametrize(
    ("yaml", "module", "task", "code"),
    [
        pytest.param(VALID_YAML, "X = 1\n", "test.unit", 0, id="skipped directory"),
        pytest.param(VALID_YAML, "X = 1\n", "format.check-python", 0, id="passing check"),
        pytest.param(VALID_YAML, "X  =  1\n", "format.check-python", 1, id="failing check"),
        pytest.param(INVALID_YAML, "X = 1\n", "test.unit", 2, id="invalid config"),
    ],
)
def test_exit_code(tmp_path: Path, yaml: str, module: str, task: str, code: int) -> None:
    project = _project(tmp_path, yaml, module)
    assert _inv(project, task).returncode == code


def test_exit_code_of_a_missing_tool(tmp_path: Path) -> None:
    project = _project(tmp_path, VALID_YAML, "X = 1\n")
    result = _inv(project, "format.check-shell", path=_bash_only(tmp_path))
    assert result.returncode == 127
