from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import testing as test_tasks
from invoke_tasklib.config import get_config

if TYPE_CHECKING:
    from collections.abc import Callable

    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture(autouse=True)
def _fixed_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


@pytest.fixture
def test_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("integration", "functional", "benchmarks"):
        (tmp_path / "tests" / name).mkdir(parents=True)
    monkeypatch.chdir(tmp_path)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


def _touch(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")


def test_doctest_markdown(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    _touch(tmp_path, "README.md", "docs/index.md", ".venv/lib/pkg/README.md")
    monkeypatch.chdir(tmp_path)

    c = _context()
    test_tasks.doctest_markdown(c)
    assert _commands(c) == [
        "/venv/bin/python -m doctest -o NORMALIZE_WHITESPACE -o ELLIPSIS -o REPORT_NDIFF README.md docs/index.md"
    ]


@pytest.mark.usefixtures("empty_project")
def test_doctest_markdown_no_files() -> None:
    c = _context()
    test_tasks.doctest_markdown(c)
    assert _commands(c) == []


@pytest.mark.parametrize(
    "excluded",
    [
        ".venv/lib/pkg/README.md",
        ".pytest_cache/README.md",
        ".git/README.md",
        "node_modules/pkg/README.md",
        "site/index.md",
        "build/lib/README.md",
        "dist/README.md",
        "htmlcov/README.md",
        ".tox/py/README.md",
        ".nox/s/README.md",
        ".mypy_cache/README.md",
        ".ruff_cache/README.md",
    ],
)
def test_doctest_markdown_excludes_dir(
    tmp_path: Path, monkeypatch: MonkeyPatch, excluded: str
) -> None:
    _touch(tmp_path, "README.md", excluded)
    monkeypatch.chdir(tmp_path)

    c = _context()
    test_tasks.doctest_markdown(c)
    assert _commands(c) == [
        "/venv/bin/python -m doctest -o NORMALIZE_WHITESPACE -o ELLIPSIS -o REPORT_NDIFF README.md"
    ]


def test_doctest_markdown_sorts_files(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    _touch(tmp_path, "docs/z.md", "docs/a.md", "README.md")
    monkeypatch.chdir(tmp_path)

    c = _context()
    test_tasks.doctest_markdown(c)
    assert _commands(c) == [
        "/venv/bin/python -m doctest -o NORMALIZE_WHITESPACE -o ELLIPSIS -o REPORT_NDIFF README.md docs/a.md docs/z.md"
    ]


def test_doctest_markdown_quotes_file_names(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    _touch(tmp_path, "my docs/a b.md")
    monkeypatch.chdir(tmp_path)

    c = _context()
    test_tasks.doctest_markdown(c)
    assert _commands(c) == [
        "/venv/bin/python -m doctest -o NORMALIZE_WHITESPACE -o ELLIPSIS -o REPORT_NDIFF 'my docs/a b.md'"
    ]


def test_doctest_src_quotes_the_source_path() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"src": "my src"}})
    test_tasks.doctest_src(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest 'my src'"]


def test_doctest_src_with_args_and_paths() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.doctest_src(c, args="-x", paths="src/a.py")
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest -x src/a.py"]


def test_doctest_markdown_with_paths(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    _touch(tmp_path, "README.md")
    monkeypatch.chdir(tmp_path)
    c = _context()
    test_tasks.doctest_markdown(c, paths="docs/a.md")
    assert _commands(c) == [
        "/venv/bin/python -m doctest -o NORMALIZE_WHITESPACE -o ELLIPSIS -o REPORT_NDIFF docs/a.md"
    ]


def test_doctest_markdown_with_args(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    _touch(tmp_path, "README.md")
    monkeypatch.chdir(tmp_path)
    c = _context()
    test_tasks.doctest_markdown(c, args="-v")
    assert _commands(c) == [
        "/venv/bin/python -m doctest -o NORMALIZE_WHITESPACE -o ELLIPSIS -o REPORT_NDIFF -v README.md"
    ]


def test_doctest_src() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"src": "src/mypkg"}})
    test_tasks.doctest_src(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest src/mypkg"]


def test_doctest(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    _touch(tmp_path, "README.md")
    monkeypatch.chdir(tmp_path)

    c = _context({"package": {"name": "mypkg"}, "paths": {"src": "src/mypkg"}})
    test_tasks.doctest(c)
    assert _commands(c) == [
        "/venv/bin/python -m pytest --xdoctest src/mypkg",
        "/venv/bin/python -m doctest -o NORMALIZE_WHITESPACE -o ELLIPSIS -o REPORT_NDIFF README.md",
    ]


def test_all_without_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.all_(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 60 tests"]


def test_all_with_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.all_(c, cov=True)
    assert _commands(c) == [
        (
            "/venv/bin/python -m pytest --xdoctest --timeout 60 "
            "--cov-report html --cov-report xml --cov-report term --cov=mypkg tests"
        )
    ]


def test_unit_with_configured_coverage_reports() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_reports": "xml,term-missing"}})
    test_tasks.unit(c, cov=True)
    assert _commands(c) == [
        (
            "/venv/bin/python -m pytest --xdoctest --timeout 10 "
            "--cov-report xml --cov-report term-missing --cov=mypkg tests/unit"
        )
    ]


def test_unit_with_no_coverage_report_has_no_report_option() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_reports": ""}})
    test_tasks.unit(c, cov=True)
    assert _commands(c) == [
        "/venv/bin/python -m pytest --xdoctest --timeout 10 --cov=mypkg tests/unit"
    ]


def test_cov_reports_are_ignored_without_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_reports": "xml"}})
    test_tasks.unit(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 10 tests/unit"]


def test_unit_without_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 10 tests/unit"]


def test_unit_with_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c, cov=True)
    assert _commands(c) == [
        (
            "/venv/bin/python -m pytest --xdoctest --timeout 10 "
            "--cov-report html --cov-report xml --cov-report term --cov=mypkg tests/unit"
        )
    ]


@pytest.mark.usefixtures("test_dirs")
def test_integration_without_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.integration(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 60 tests/integration"]


@pytest.mark.usefixtures("test_dirs")
def test_integration_with_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.integration(c, cov=True)
    assert _commands(c) == [
        (
            "/venv/bin/python -m pytest --xdoctest --timeout 60 --cov-report html --cov-report xml "
            "--cov-report term --cov-append --cov=mypkg tests/integration"
        )
    ]


@pytest.mark.usefixtures("test_dirs")
def test_functional_without_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.functional(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 60 tests/functional"]


@pytest.mark.usefixtures("test_dirs")
def test_functional_with_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.functional(c, cov=True)
    assert _commands(c) == [
        (
            "/venv/bin/python -m pytest --xdoctest --timeout 60 --cov-report html --cov-report xml "
            "--cov-report term --cov-append --cov=mypkg tests/functional"
        )
    ]


def test_all_uses_the_largest_timeout() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"functional_timeout": 300}})
    test_tasks.all_(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 300 tests"]


def test_unit_uses_configured_timeout() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"unit_timeout": 3}})
    test_tasks.unit(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 3 tests/unit"]


@pytest.mark.usefixtures("test_dirs")
def test_integration_uses_configured_timeout() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"integration_timeout": 7}})
    test_tasks.integration(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 7 tests/integration"]


@pytest.mark.usefixtures("test_dirs")
def test_functional_uses_configured_timeout() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"functional_timeout": 9}})
    test_tasks.functional(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 9 tests/functional"]


def test_unit_without_xdoctest() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"xdoctest": False}})
    test_tasks.unit(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --timeout 10 tests/unit"]


def test_unit_with_coverage_forwards_fail_under() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_fail_under": 95}})
    test_tasks.unit(c, cov=True)
    assert _commands(c) == [
        (
            "/venv/bin/python -m pytest --xdoctest --timeout 10 "
            "--cov-report html --cov-report xml --cov-report term --cov=mypkg "
            "--cov-fail-under=95 tests/unit"
        )
    ]


def test_unit_without_coverage_ignores_fail_under() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_fail_under": 95}})
    test_tasks.unit(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 10 tests/unit"]


def test_fail_under_zero_is_forwarded() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_fail_under": 0}})
    test_tasks.unit(c, cov=True)
    assert "--cov-fail-under=0" in _commands(c)[0]


def test_unit_coverage_uses_the_import_name() -> None:
    c = _context({"package": {"name": "my-pkg"}})
    test_tasks.unit(c, cov=True)
    assert "--cov=my_pkg" in _commands(c)[0]


def test_unit_args() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c, args="-k foo -x")
    assert _commands(c) == [
        "/venv/bin/python -m pytest --xdoctest --timeout 10 -k foo -x tests/unit"
    ]


def test_unit_args_are_quoted() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c, args='-k "a or b"')
    assert _commands(c) == [
        "/venv/bin/python -m pytest --xdoctest --timeout 10 -k 'a or b' tests/unit"
    ]


def test_unit_paths_replace_the_unit_tests_directory() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c, paths="tests/unit/test_a.py")
    assert _commands(c) == [
        "/venv/bin/python -m pytest --xdoctest --timeout 10 tests/unit/test_a.py"
    ]


def test_unit_args_come_after_coverage_options() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c, cov=True, args="-x")
    assert _commands(c) == [
        (
            "/venv/bin/python -m pytest --xdoctest --timeout 10 "
            "--cov-report html --cov-report xml --cov-report term --cov=mypkg -x tests/unit"
        )
    ]


def test_all_args_and_paths() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.all_(c, args="-x", paths="tests/unit tests/integration")
    assert _commands(c) == [
        "/venv/bin/python -m pytest --xdoctest --timeout 60 -x tests/unit tests/integration"
    ]


@pytest.mark.usefixtures("empty_project")
def test_integration_paths_run_even_if_the_directory_is_missing() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.integration(c, paths="tests/integration/test_a.py")
    assert _commands(c) == [
        "/venv/bin/python -m pytest --xdoctest --timeout 60 tests/integration/test_a.py"
    ]


@pytest.mark.usefixtures("test_dirs")
def test_functional_args() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.functional(c, args="-x")
    assert _commands(c) == [
        "/venv/bin/python -m pytest --xdoctest --timeout 60 -x tests/functional"
    ]


def test_coverage_report() -> None:
    c = _context()
    test_tasks.coverage_report(c)
    assert _commands(c) == [
        "/venv/bin/python -m coverage html",
        "/venv/bin/python -m coverage report",
    ]


def test_coverage_report_with_args() -> None:
    c = _context()
    test_tasks.coverage_report(c, args="--fail-under=90")
    assert _commands(c) == [
        "/venv/bin/python -m coverage html",
        "/venv/bin/python -m coverage report --fail-under=90",
    ]


def test_coverage_report_open_browser() -> None:
    c = _context()
    test_tasks.coverage_report(c, open_browser=True)
    assert _commands(c) == [
        "/venv/bin/python -m coverage html",
        "/venv/bin/python -m coverage report",
        "/venv/bin/python -m webbrowser -t htmlcov/index.html",
    ]


@pytest.mark.usefixtures("empty_project")
def test_benchmark_quotes_the_benchmarks_path(tmp_path: Path) -> None:
    (tmp_path / "my bench").mkdir()
    c = _context({"package": {"name": "mypkg"}, "paths": {"benchmarks": "my bench"}})
    test_tasks.benchmark(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --benchmark-only 'my bench/'"]


@pytest.mark.usefixtures("test_dirs")
def test_benchmark_with_args() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.benchmark(c, args="--benchmark-save=x")
    assert _commands(c) == [
        "/venv/bin/python -m pytest --benchmark-only --benchmark-save=x tests/benchmarks/"
    ]


@pytest.mark.usefixtures("empty_project")
def test_benchmark_with_paths_runs_without_the_default_directory() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.benchmark(c, paths="bench/test_a.py")
    assert _commands(c) == ["/venv/bin/python -m pytest --benchmark-only bench/test_a.py"]


@pytest.mark.usefixtures("test_dirs")
def test_benchmark() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.benchmark(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --benchmark-only tests/benchmarks/"]


##############################################
#     Tests for missing test directories     #
##############################################


@pytest.fixture
def empty_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


@pytest.mark.usefixtures("empty_project")
@pytest.mark.parametrize("task", [test_tasks.integration, test_tasks.functional])
def test_scope_without_directory_runs_nothing(task: Callable[..., None]) -> None:
    c = _context({"package": {"name": "mypkg"}})
    task(c)
    assert _commands(c) == []


@pytest.mark.usefixtures("empty_project")
def test_benchmark_without_directory_runs_nothing() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.benchmark(c)
    assert _commands(c) == []


@pytest.mark.usefixtures("empty_project")
def test_integration_without_directory_says_it_skips(capsys: pytest.CaptureFixture[str]) -> None:
    test_tasks.integration(_context({"package": {"name": "mypkg"}}))
    assert capsys.readouterr().out == (
        "⏭️  No 'tests/integration' directory: skipping integration tests\n"
    )


@pytest.mark.usefixtures("empty_project")
def test_unit_without_any_tests_directory_runs_nothing() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c)
    assert _commands(c) == []


@pytest.mark.usefixtures("empty_project")
def test_unit_without_any_tests_directory_says_it_skips(
    capsys: pytest.CaptureFixture[str],
) -> None:
    test_tasks.unit(_context({"package": {"name": "mypkg"}}))
    assert capsys.readouterr().out == "⏭️  No 'tests/unit' directory: skipping unit tests\n"


def test_unit_with_a_flat_tests_directory_runs_the_tests_directory(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    (tmp_path / "tests").mkdir()
    monkeypatch.chdir(tmp_path)
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 10 tests"]


def test_unit_with_a_flat_tests_directory_says_it_falls_back(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "tests").mkdir()
    monkeypatch.chdir(tmp_path)
    test_tasks.unit(_context({"package": {"name": "mypkg"}}))
    assert capsys.readouterr().out.startswith(
        "⏭️  No 'tests/unit' directory: running 'tests' instead\n"
    )


def test_unit_with_a_unit_directory_runs_it(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 10 tests/unit"]


@pytest.mark.usefixtures("empty_project")
def test_unit_with_paths_does_not_fall_back() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c, paths="tests/test_a.py")
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 10 tests/test_a.py"]


def test_unit_with_custom_tests_directory_falls_back_to_it(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    (tmp_path / "spec").mkdir()
    monkeypatch.chdir(tmp_path)
    c = _context({"package": {"name": "mypkg"}, "paths": {"tests": "spec"}})
    test_tasks.unit(c)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 10 spec"]


##########################################
#     Tests for _find_markdown_files     #
##########################################


def test_find_markdown_files_returns_sorted_paths(tmp_path: Path) -> None:
    _touch(tmp_path, "docs/z.md", "README.md", "docs/a.md")
    assert test_tasks._find_markdown_files(tmp_path) == [
        tmp_path / "README.md",
        tmp_path / "docs" / "a.md",
        tmp_path / "docs" / "z.md",
    ]


def test_find_markdown_files_empty(tmp_path: Path) -> None:
    assert test_tasks._find_markdown_files(tmp_path) == []


def test_find_markdown_files_ignores_other_extensions(tmp_path: Path) -> None:
    _touch(tmp_path, "a.txt", "b.mdx", "c.md.bak", "d.md")
    assert test_tasks._find_markdown_files(tmp_path) == [tmp_path / "d.md"]


@pytest.mark.parametrize("excluded", sorted(test_tasks.MARKDOWN_EXCLUDED_DIRS))
def test_find_markdown_files_does_not_walk_into_excluded_dirs(
    tmp_path: Path, excluded: str
) -> None:
    _touch(tmp_path, f"{excluded}/a.md", "b.md")
    assert test_tasks._find_markdown_files(tmp_path) == [tmp_path / "b.md"]


def test_find_markdown_files_skips_excluded_dirs_at_any_depth(tmp_path: Path) -> None:
    _touch(tmp_path, "pkg/.venv/a.md", "pkg/b.md")
    assert test_tasks._find_markdown_files(tmp_path) == [tmp_path / "pkg" / "b.md"]


def test_find_markdown_files_current_directory_has_no_prefix(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    _touch(tmp_path, "README.md")
    monkeypatch.chdir(tmp_path)
    assert test_tasks._find_markdown_files(Path()) == [Path("README.md")]


#######################################
#     Tests for _directory_exists     #
#######################################


def test_directory_exists_true_for_existing_directory(tmp_path: Path) -> None:
    assert test_tasks._directory_exists(_context(), str(tmp_path), "x") is True


def test_directory_exists_false_for_missing_directory(tmp_path: Path) -> None:
    assert test_tasks._directory_exists(_context(), str(tmp_path / "missing"), "x") is False


def test_directory_exists_false_for_file(tmp_path: Path) -> None:
    (tmp_path / "f").write_text("")
    assert test_tasks._directory_exists(_context(), str(tmp_path / "f"), "x") is False


def test_directory_exists_is_silent_when_present(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    test_tasks._directory_exists(_context(), str(tmp_path), "x")
    assert capsys.readouterr().out == ""


#################################
#     Tests for _run_pytest     #
#################################


def test_run_pytest_says_it_starts(capsys: pytest.CaptureFixture[str]) -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks._run_pytest(c, "tests/x", label="x tests", timeout=1)
    assert capsys.readouterr().out == "🧪 Running x tests...\n✅ X tests complete\n"


def test_run_pytest_says_coverage_is_generated(capsys: pytest.CaptureFixture[str]) -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks._run_pytest(c, "tests/x", label="x tests", timeout=1, cov=True)
    assert "📊 Coverage reports will be generated\n" in capsys.readouterr().out


def test_run_pytest_says_coverage_is_appended(capsys: pytest.CaptureFixture[str]) -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks._run_pytest(c, "tests/x", label="x tests", timeout=1, cov=True, append=True)
    assert "📊 Coverage reports will be generated (appending)\n" in capsys.readouterr().out


def test_run_pytest_append_without_cov_is_ignored() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks._run_pytest(c, "tests/x", label="x tests", timeout=1, append=True)
    assert _commands(c) == ["/venv/bin/python -m pytest --xdoctest --timeout 1 tests/x"]


@pytest.mark.usefixtures("empty_project")
def test_run_pytest_skip_missing_runs_nothing() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks._run_pytest(c, "tests/x", label="x tests", timeout=1, skip_missing=True)
    assert _commands(c) == []


@pytest.mark.usefixtures("empty_project")
def test_run_pytest_without_skip_missing_runs_a_missing_directory() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks._run_pytest(c, "tests/x", label="x tests", timeout=1)
    assert len(_commands(c)) == 1


def test_run_pytest_uses_the_given_config_without_reading_the_context() -> None:
    c = MockContext(config=Config(), run=True)
    cfg = get_config(_context({"package": {"name": "mypkg"}, "test": {"xdoctest": False}}))
    test_tasks._run_pytest(c, "tests/x", label="x tests", timeout=5, cfg=cfg)
    assert _commands(c) == ["/venv/bin/python -m pytest --timeout 5 tests/x"]


def test_run_pytest_loads_the_config_without_a_given_one() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"xdoctest": False}})
    test_tasks._run_pytest(c, "tests/x", label="x tests", timeout=5)
    assert _commands(c) == ["/venv/bin/python -m pytest --timeout 5 tests/x"]
