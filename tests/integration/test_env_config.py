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


VERSION_TASKS = TASKS.replace(
    "cfg.paths.src, cfg.test.unit_timeout", "cfg.package.python_version, cfg.test.unit_timeout"
)


def _show(project: Path, tasks: str = TASKS, **env: str) -> str:
    (project / "tasks.py").write_text(tasks)
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


def test_environment_variable_false_turns_a_boolean_off(tmp_path: Path) -> None:
    assert _show(tmp_path, INVOKE_TASKLIB_TEST_XDOCTEST="false") == "src/demo 10 False None"


def test_environment_variable_yes_turns_a_boolean_on(tmp_path: Path) -> None:
    assert _show(tmp_path, INVOKE_TASKLIB_TEST_XDOCTEST="Yes") == "src/demo 10 True None"


def test_environment_variable_sets_the_coverage_threshold(tmp_path: Path) -> None:
    assert _show(tmp_path, INVOKE_TASKLIB_TEST_COV_FAIL_UNDER="90") == "src/demo 10 True 90"


def test_python_version_is_not_derived_from_the_python_version_file(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("3.12\n")
    assert _show(tmp_path, tasks=VERSION_TASKS).split()[0] == "None"


def test_python_version_is_not_derived_from_requires_python(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.11"\n')
    assert _show(tmp_path, tasks=VERSION_TASKS).split()[0] == "None"


def _config_show(project: Path, **env: str) -> list[str]:
    (project / "tasks.py").write_text("from invoke_tasklib import make_ns\n\nns = make_ns()\n")
    (project / "invoke.yaml").write_text(
        "tasklib:\n  package:\n    name: demo\n  paths:\n    src: lib\n"
    )
    proc = subprocess.run(
        [sys.executable, "-m", "invoke", "config.show"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **env},
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.splitlines()


def test_config_show_reports_the_project_file(tmp_path: Path) -> None:
    assert "    src: lib  # project file" in _config_show(tmp_path)


def test_config_show_reports_a_default(tmp_path: Path) -> None:
    assert "    tests: tests  # default" in _config_show(tmp_path)


def test_config_show_reports_a_derived_value(tmp_path: Path) -> None:
    assert "    unit_tests: tests/unit  # derived" in _config_show(tmp_path)


def test_config_show_reports_an_environment_variable(tmp_path: Path) -> None:
    lines = _config_show(tmp_path, INVOKE_TASKLIB_TEST_UNIT_TIMEOUT="30")
    assert "    unit_timeout: 30  # environment variable INVOKE_TASKLIB_TEST_UNIT_TIMEOUT" in lines


def test_config_show_reports_a_default_boolean(tmp_path: Path) -> None:
    assert "    xdoctest: true  # default" in _config_show(tmp_path)


def test_config_show_reports_a_boolean_from_the_environment(tmp_path: Path) -> None:
    lines = _config_show(tmp_path, INVOKE_TASKLIB_TEST_XDOCTEST="false")
    assert "    xdoctest: false  # environment variable INVOKE_TASKLIB_TEST_XDOCTEST" in lines


def test_config_show_reports_a_string_from_the_environment(tmp_path: Path) -> None:
    lines = _config_show(tmp_path, INVOKE_TASKLIB_TYPES_CHECKER="mypy")
    assert "    checker: mypy  # environment variable INVOKE_TASKLIB_TYPES_CHECKER" in lines


def test_config_show_reports_a_list_from_the_environment(tmp_path: Path) -> None:
    lines = _config_show(tmp_path, INVOKE_TASKLIB_GROUPS_INSTALL="dev,docs")
    assert "    install: [dev, docs]  # environment variable INVOKE_TASKLIB_GROUPS_INSTALL" in lines


def test_invalid_integer_variable_exits_with_a_message(tmp_path: Path) -> None:
    (tmp_path / "tasks.py").write_text("from invoke_tasklib import make_ns\n\nns = make_ns()\n")
    (tmp_path / "invoke.yaml").write_text("tasklib:\n  package:\n    name: demo\n")
    proc = subprocess.run(
        [sys.executable, "-m", "invoke", "config.show"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "INVOKE_TASKLIB_TEST_UNIT_TIMEOUT": "abc"},
    )
    assert (proc.returncode, "must be an integer >= 1, got 'abc'" in proc.stderr) == (2, True)


def _show_failure(project: Path, invoke_yaml: str) -> subprocess.CompletedProcess[str]:
    (project / "tasks.py").write_text(TASKS)
    (project / "invoke.yaml").write_text(invoke_yaml)
    return subprocess.run(
        [sys.executable, "-m", "invoke", "show"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_null_integer_in_invoke_yaml_is_an_error(tmp_path: Path) -> None:
    proc = _show_failure(
        tmp_path, "tasklib:\n  package:\n    name: demo\n  test:\n    unit_timeout: ~\n"
    )
    assert "'tasklib.test.unit_timeout' must be an integer" in proc.stderr


def test_a_null_boolean_in_invoke_yaml_is_an_error(tmp_path: Path) -> None:
    proc = _show_failure(
        tmp_path, "tasklib:\n  package:\n    name: demo\n  test:\n    xdoctest: null\n"
    )
    assert "'tasklib.test.xdoctest' must be a boolean" in proc.stderr
