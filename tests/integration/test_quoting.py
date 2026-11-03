from __future__ import annotations

from typing import TYPE_CHECKING

from invoke_tasklib import testing
from tests.integration.test_imports import _context

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_doctest_markdown_runs_a_file_with_a_space(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "my docs").mkdir()
    (tmp_path / "my docs" / "a b.md").write_text(">>> 1 + 1\n2\n")
    monkeypatch.chdir(tmp_path)
    testing.doctest_markdown(_context("mypkg"))
    assert "✅ All 1 markdown files have been checked" in capsys.readouterr().out
