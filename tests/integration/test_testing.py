from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from invoke.config import Config
from invoke.exceptions import Exit

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


@pytest.fixture
def scoped_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "__init__.py").write_text("")
    for module in ("one", "two"):
        (tmp_path / "demo" / f"{module}.py").write_text("def run():\n    return 1\n")
    for scope, module in (("unit", "one"), ("integration", "two")):
        (tmp_path / "tests" / scope).mkdir(parents=True)
        (tmp_path / "tests" / scope / f"test_{module}.py").write_text(
            f"from demo import {module}\n\n\ndef test_run():\n    assert {module}.run() == 1\n"
        )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _covered_files(project: Path) -> list[str]:
    xml = (project / "coverage.xml").read_text()
    classes = re.findall(r'filename="(one|two)\.py"[^>]*line-rate="([\d.]+)"', xml)
    return sorted(f"{name}.py" for name, rate in classes if float(rate) > 0)


def _run_scopes(*, append: bool) -> None:
    testing.unit(_context(cov_reports="xml"), cov=True, args="-p no:cacheprovider")
    testing.integration(
        _context(cov_reports="xml"), cov=True, append=append, args="-p no:cacheprovider"
    )


def test_integration_coverage_replaces_the_data_by_default(scoped_project: Path) -> None:
    _run_scopes(append=False)
    assert _covered_files(scoped_project) == ["two.py"]


def test_integration_coverage_appends_on_request(scoped_project: Path) -> None:
    _run_scopes(append=True)
    assert _covered_files(scoped_project) == ["one.py", "two.py"]


def test_unit_with_coverage_moves_a_report_with_an_argument(flat_project: Path) -> None:
    testing.unit(_context(cov_reports="xml:out/cov.xml"), cov=True, args="-p no:cacheprovider")
    assert (flat_project / "out" / "cov.xml").is_file()


@pytest.mark.usefixtures("flat_project")
def test_unit_with_coverage_accepts_term_missing_skip_covered(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reports = "term-missing:skip-covered"
    testing.unit(_context(cov_reports=reports), cov=True, args="-p no:cacheprovider")
    assert "✅ Unit tests complete" in capsys.readouterr().out


@pytest.mark.usefixtures("flat_project")
def test_benchmark_without_directory_fails() -> None:
    with pytest.raises(Exit, match=r"No 'tests/benchmarks' directory"):
        testing.benchmark(_context())


def test_benchmark_measures_a_benchmark_file(flat_project: Path) -> None:
    (flat_project / "bench").mkdir()
    (flat_project / "bench" / "test_b.py").write_text(
        "def test_b(benchmark):\n    assert benchmark(sum, [1, 2]) == 3\n"
    )
    assert testing.benchmark(_context(), args="-p no:cacheprovider", paths="bench") is None


def test_doctest_markdown_does_not_walk_into_the_venv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "README.md").write_text(">>> 1 / 0\n")
    (tmp_path / "README.md").write_text(">>> 1 + 1\n2\n")
    monkeypatch.chdir(tmp_path)
    testing.doctest_markdown(_context())
    assert "✅ All 1 markdown files have been checked" in capsys.readouterr().out
