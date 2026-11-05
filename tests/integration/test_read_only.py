from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src"
TASKS = "from invoke_tasklib import make_ns\n\nns = make_ns()\n"
INVOKE_YAML = 'tasklib:\n  package:\n    name: demo\n    python_version: "3.10"\n'
GITIGNORE = ".ruff_cache/\n.pytest_cache/\n__pycache__/\n.coverage\ncoverage.xml\nhtmlcov/\n"


def _run(project: Path, *command: str) -> subprocess.CompletedProcess[str]:
    r"""Run a command in ``project`` with the real Invoke runner.

    The ``PATH`` starts with the directory of the running interpreter,
    so the tools of the virtual environment are found, and
    ``PYTHONPATH`` has the project and the source of the package.
    """
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(SRC), str(project)]),
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
    }
    return subprocess.run(  # noqa: S603 (fixed commands)
        command, cwd=project, capture_output=True, text=True, check=False, env=env
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    r"""Create a committed git project that uses ``invoke_tasklib``."""
    (tmp_path / "tasks.py").write_text(TASKS)
    (tmp_path / "invoke.yaml").write_text(INVOKE_YAML)
    (tmp_path / ".gitignore").write_text(GITIGNORE)
    (tmp_path / "demo.py").write_text('def one():\n    r"""Return 1."""\n    return 1\n')
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_a.py").write_text(
        "import demo\n\n\ndef test_a():\n    assert demo.one() == 1\n"
    )
    _run(tmp_path, "git", "init", "-q")
    _run(tmp_path, "git", "add", ".")
    _run(
        tmp_path,
        *("git", "-c", "user.name=t", "-c", "user.email=t@example.com"),
        *("commit", "-q", "-m", "init"),
    )
    return tmp_path


##################################
#     Tests for the read-only    #
##################################


@pytest.mark.parametrize(
    "task",
    [
        "format.check-python",
        "lint.check-python",
        "types.check",
        "test.unit",
        "test.doctest",
        "imports.check-cycles",
        "config.show",
    ],
)
def test_read_only_task_leaves_the_work_tree_clean(project: Path, task: str) -> None:
    _run(project, sys.executable, "-m", "invoke", task)
    status = _run(project, "git", "status", "--porcelain")
    assert status.stdout == ""
