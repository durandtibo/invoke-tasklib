from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

TASKS = """
from invoke import task
from invoke_tasklib import make_ns
from invoke_tasklib.config import get_config


@task
def show(c):
    cfg = get_config(c)
    print(cfg.paths.src, cfg.test.unit_timeout, cfg.test.xdoctest, cfg.test.cov_fail_under)


ns = make_ns()
ns.add_task(show)
"""


def _show(project: Path, **env: str) -> str:
    (project / "tasks.py").write_text(TASKS)
    (project / "invoke.yaml").write_text("tasklib:\n  package:\n    name: demo\n")
    proc = subprocess.run(
        [sys.executable, "-m", "invoke", "show"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **env},
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_environment_variables_are_ignored_when_not_set(tmp_path: Path) -> None:
    assert _show(tmp_path) == "src/demo 10 True None"


def test_environment_variable_overrides_a_path(tmp_path: Path) -> None:
    assert _show(tmp_path, INVOKE_TASKLIB_PATHS_SRC="zzz") == "zzz 10 True None"


def test_environment_variable_overrides_a_timeout(tmp_path: Path) -> None:
    assert _show(tmp_path, INVOKE_TASKLIB_TEST_UNIT_TIMEOUT="33") == "src/demo 33 True None"


def test_environment_variable_overrides_a_boolean(tmp_path: Path) -> None:
    assert _show(tmp_path, INVOKE_TASKLIB_TEST_XDOCTEST="0") == "src/demo 10 False None"


def test_environment_variable_sets_the_coverage_threshold(tmp_path: Path) -> None:
    assert _show(tmp_path, INVOKE_TASKLIB_TEST_COV_FAIL_UNDER="90") == "src/demo 10 True 90"
