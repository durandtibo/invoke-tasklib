from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from invoke.exceptions import Exit, UnexpectedExit

from invoke_tasklib import check
from tests.integration.test_imports import _context, _write

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def broken_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"badpkg/__init__.py": "", "badpkg/a.py": "import missing_module\n"})
    return tmp_path


@pytest.mark.usefixtures("broken_project")
def test_all_stops_with_the_error_of_the_step() -> None:
    with pytest.raises(UnexpectedExit):
        check.all_(_context("badpkg"), only="imports")


@pytest.mark.usefixtures("broken_project")
def test_all_keep_going_reports_the_failed_step() -> None:
    with pytest.raises(Exit, match=r"1 of 1 check\(s\) failed: imports"):
        check.all_(_context("badpkg"), only="imports", keep_going=True)
