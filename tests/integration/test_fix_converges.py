from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src"
TASKS = "from invoke_tasklib import make_ns\n\nns = make_ns()\n"
INVOKE_YAML = 'tasklib:\n  package:\n    name: demo\n    python_version: "3.10"\n'
RUFF_TOML = 'line-length = 100\n\n[lint]\nselect = ["E", "F", "I"]\n'
BAD_MODULE = (
    "import sys\nimport os\n\n\ndef one( x ):\n    r'''Return x.'''\n    return  os.sep+str(x)\n"
)
_STEPS = "format-python,lint"


def _run(project: Path, *command: str) -> subprocess.CompletedProcess[str]:
    r"""Run a command in ``project`` with the real Invoke runner."""
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
    r"""Create a committed git project with code that needs fixing."""
    (tmp_path / "tasks.py").write_text(TASKS)
    (tmp_path / "invoke.yaml").write_text(INVOKE_YAML)
    (tmp_path / "ruff.toml").write_text(RUFF_TOML)
    (tmp_path / "demo.py").write_text(BAD_MODULE)
    _run(tmp_path, "git", "init", "-q")
    _run(tmp_path, "git", "add", ".")
    _run(
        tmp_path,
        *("git", "-c", "user.name=t", "-c", "user.email=t@example.com"),
        *("commit", "-q", "-m", "init"),
    )
    return tmp_path


def test_check_fails_before_the_fix(project: Path) -> None:
    assert _run(project, "inv", "check", "--only", _STEPS).returncode == 1


def test_fix_all_succeeds(project: Path) -> None:
    assert _run(project, "inv", "fix.all", "--only", _STEPS).returncode == 0


def test_check_passes_after_fix_all(project: Path) -> None:
    _run(project, "inv", "fix.all", "--only", _STEPS)
    assert _run(project, "inv", "check", "--only", _STEPS).returncode == 0


def test_second_fix_all_changes_nothing(project: Path) -> None:
    _run(project, "inv", "fix.all", "--only", _STEPS)
    first = (project / "demo.py").read_text()
    _run(project, "inv", "fix.all", "--only", _STEPS)
    assert (project / "demo.py").read_text() == first
