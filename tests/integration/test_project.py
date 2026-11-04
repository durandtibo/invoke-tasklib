from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src"
TASKS = "from invoke_tasklib import make_ns\n\nns = make_ns()\n"
INVOKE_YAML = 'tasklib:\n  package:\n    name: demo\n    python_version: "3.10"\n'


def _inv(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    r"""Run ``inv`` in ``project`` with the real Invoke runner.

    The ``PATH`` starts with the directory of the running interpreter,
    so the tools of the virtual environment (``ruff``) are found.
    """
    env = {
        **os.environ,
        "PYTHONPATH": str(SRC),
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
    }
    return subprocess.run(  # noqa: S603 (fixed command)
        [sys.executable, "-m", "invoke", *args],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    r"""Create a tiny project that uses ``invoke_tasklib``."""
    (tmp_path / "tasks.py").write_text(TASKS)
    (tmp_path / "invoke.yaml").write_text(INVOKE_YAML)
    (tmp_path / "demo.py").write_text("def one():\n    return 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text(
        "import demo\n\n\ndef test_a():\n    assert demo.one() == 1\n"
    )
    return tmp_path


###############################
#     Tests for inv --list    #
###############################


def test_list_succeeds(project: Path) -> None:
    assert _inv(project, "--list").returncode == 0


@pytest.mark.parametrize(
    "task",
    [
        "check.all",
        "clean.all",
        "doc.build",
        "env.install",
        "format.check-python",
        "imports.check-cycles",
        "lint.check-python",
        "release.build",
        "security.audit",
        "test.unit",
        "types.check",
    ],
)
def test_list_contains_the_task(project: Path, task: str) -> None:
    assert f"  {task} " in _inv(project, "--list").stdout


def test_list_summaries_have_no_backticks(project: Path) -> None:
    assert "`" not in _inv(project, "--list").stdout


########################################
#     Tests for the tasks end to end   #
########################################


def test_format_check_python_passes_on_a_formatted_project(project: Path) -> None:
    assert _inv(project, "format.check-python").returncode == 0


def test_format_check_python_fails_on_an_unformatted_file(project: Path) -> None:
    (project / "demo.py").write_text("def one( ):\n  return 1\n")
    assert _inv(project, "format.check-python").returncode == 1


def test_test_unit_runs_the_tests(project: Path) -> None:
    proc = _inv(project, "test.unit", "--args", "-p no:cacheprovider")
    assert "1 passed" in proc.stdout


def test_test_unit_fails_on_a_failing_test(project: Path) -> None:
    (project / "tests" / "test_a.py").write_text("def test_a():\n    assert False\n")
    assert _inv(project, "test.unit", "--args", "-p no:cacheprovider").returncode == 1


def test_clean_pycache_removes_the_directories(project: Path) -> None:
    (project / "__pycache__").mkdir()
    _inv(project, "clean.pycache")
    assert not (project / "__pycache__").exists()


#####################################
#     Tests for an invalid config   #
#####################################


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (
            "tasklib:\n  package:\n    name: demo\n    python_version: 3.10\n",
            r"must be a string like",
        ),
        ("tasklib:\n  unknown: 1\n", r"unknown"),
        (
            "tasklib:\n  package:\n    name: demo\n  test:\n    cov_fail_under: abc\n",
            r"cov_fail_under",
        ),
    ],
)
def test_invalid_config_exits_with_a_message(project: Path, config: str, message: str) -> None:
    (project / "invoke.yaml").write_text(config)
    assert re.search(message, _inv(project, "test.unit").stderr)


def test_invalid_config_exits_with_code_2(project: Path) -> None:
    (project / "invoke.yaml").write_text("tasklib:\n  unknown: 1\n")
    assert _inv(project, "test.unit").returncode == 2


#######################################
#     Tests for a subdirectory        #
#######################################


def test_task_from_a_subdirectory_exits_with_a_message(project: Path) -> None:
    (project / "sub").mkdir()
    proc = _inv(project / "sub", "test.unit")
    assert (proc.returncode, "inv must run from the project root" in proc.stderr) == (2, True)


def test_task_from_a_subdirectory_does_not_skip_the_tests(project: Path) -> None:
    (project / "sub").mkdir()
    proc = _inv(project / "sub", "test.unit")
    assert "skipping" not in proc.stdout


def test_task_from_the_project_root_runs(project: Path) -> None:
    proc = _inv(project, "config.show")
    assert proc.returncode == 0, proc.stderr
