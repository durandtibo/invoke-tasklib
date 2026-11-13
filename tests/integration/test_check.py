from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

import pytest
from invoke.exceptions import Exit

from invoke_tasklib import check
from tests.integration.test_imports import _context, _write

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def broken_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _write(
        tmp_path,
        {
            "badpkg/__init__.py": "",
            "badpkg/a.py": "import badpkg.b\n",
            "badpkg/b.py": "import badpkg.a\n",
        },
    )
    return tmp_path


@pytest.mark.usefixtures("broken_project")
def test_all_stops_with_the_error_of_the_step() -> None:
    with pytest.raises(Exit, match=r"badpkg\.a -> badpkg\.b -> badpkg\.a"):
        check.all_(_context("badpkg"), only="imports")


@pytest.mark.usefixtures("broken_project")
def test_all_keep_going_reports_the_failed_step() -> None:
    with pytest.raises(Exit, match=r"1 of 1 check\(s\) failed: imports"):
        check.all_(_context("badpkg"), only="imports", keep_going=True)


def test_all_keep_going_prints_the_hint_of_a_missing_tool(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    with pytest.raises(Exit, match=r"1 of 1 check\(s\) failed: shell"):
        check.all_(_context("badpkg"), only="shell", keep_going=True)
    assert re.search(r"'(shellcheck|shfmt)' was not found", capsys.readouterr().err)


def test_all_stops_before_running_when_a_tool_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(sys, "executable", "/nonexistent/python")
    with pytest.raises(Exit, match=r"tool\(s\) missing for the selected steps") as info:
        check.all_(_context("badpkg"), only="lint,imports")
    assert info.value.code == 127


def test_all_prints_nothing_when_a_tool_is_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(sys, "executable", "/nonexistent/python")
    with pytest.raises(Exit, match=r"missing"):
        check.all_(_context("badpkg"), only="lint,imports")
    assert capsys.readouterr().out == ""


def test_all_keep_going_failure_goes_to_stderr_and_progress_to_stdout(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    with pytest.raises(Exit, match=r"1 of 1 check\(s\) failed: shell"):
        check.all_(_context("badpkg"), only="shell", keep_going=True)
    captured = capfd.readouterr()
    assert (captured.out, captured.err.startswith("❌ Step failed: shell\n")) == (
        "🔎 Running all the checks...\n",
        True,
    )
