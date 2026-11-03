from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from invoke.config import Config

from invoke_tasklib import testing
from tests.integration.test_imports import _SubprocessContext

if TYPE_CHECKING:
    from pathlib import Path


def _context(**test: object) -> _SubprocessContext:
    overrides = {"tasklib": {"package": {"name": "demo"}, "test": {"xdoctest": False, **test}}}
    return _SubprocessContext(config=Config(overrides=overrides))


@pytest.fixture
def flat_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "tests").mkdir()
    (tmp_path / "demo.py").write_text("def one():\n    return 1\n")
    (tmp_path / "tests" / "test_a.py").write_text(
        "import demo\n\n\ndef test_a():\n    assert demo.one() == 1\n"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.usefixtures("flat_project")
def test_unit_runs_a_flat_tests_directory(capsys: pytest.CaptureFixture[str]) -> None:
    testing.unit(_context(), args="-p no:cacheprovider")
    assert "✅ Unit tests complete" in capsys.readouterr().out


def test_unit_does_not_create_the_unit_tests_directory(flat_project: Path) -> None:
    testing.unit(_context(), args="-p no:cacheprovider")
    assert not (flat_project / "tests" / "unit").exists()


def test_unit_with_coverage_generates_only_the_configured_reports(flat_project: Path) -> None:
    testing.unit(_context(cov_reports="xml"), cov=True, args="-p no:cacheprovider")
    assert (flat_project / "coverage.xml").is_file()


def test_unit_with_coverage_does_not_generate_the_other_reports(flat_project: Path) -> None:
    testing.unit(_context(cov_reports="xml"), cov=True, args="-p no:cacheprovider")
    assert not (flat_project / "htmlcov").exists()


def test_doctest_markdown_does_not_walk_into_the_venv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "README.md").write_text(">>> 1 / 0\n")
    (tmp_path / "README.md").write_text(">>> 1 + 1\n2\n")
    monkeypatch.chdir(tmp_path)
    testing.doctest_markdown(_context())
    assert "✅ All 1 markdown files have been checked" in capsys.readouterr().out
