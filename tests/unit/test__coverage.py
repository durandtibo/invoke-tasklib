from __future__ import annotations

import pytest

from invoke_tasklib import _coverage

_NO_PYPROJECT: dict = {}


def _coverage_table(**sections: dict[str, object]) -> dict:
    return {"tool": {"coverage": sections}}


########################################
#     Tests for _coverage_html_dir     #
########################################


def test_coverage_html_dir_without_file() -> None:
    assert _coverage._coverage_html_dir(_NO_PYPROJECT) == "htmlcov"


def test_coverage_html_dir_reads_the_option() -> None:
    pyproject = _coverage_table(html={"directory": "reports/html"})
    assert _coverage._coverage_html_dir(pyproject) == "reports/html"


def test_coverage_html_dir_without_the_option() -> None:
    assert _coverage._coverage_html_dir(_coverage_table(run={"branch": True})) == "htmlcov"


def test_coverage_html_dir_with_an_empty_option() -> None:
    assert _coverage._coverage_html_dir(_coverage_table(html={"directory": ""})) == "htmlcov"


def test_coverage_html_dir_with_a_value_that_is_not_a_string() -> None:
    assert _coverage._coverage_html_dir(_coverage_table(html={"directory": 3})) == "htmlcov"


######################################
#     Tests for coverage_outputs     #
######################################


def test_coverage_outputs_defaults() -> None:
    assert _coverage.coverage_outputs(["html", "xml", "term"], _NO_PYPROJECT) == (
        "htmlcov",
        ("coverage.xml",),
    )


def test_coverage_outputs_without_reports_has_the_default_html_dir() -> None:
    assert _coverage.coverage_outputs([], _NO_PYPROJECT) == ("htmlcov", ())


def test_coverage_outputs_reads_pyproject() -> None:
    pyproject = _coverage_table(
        html={"directory": "h"},
        xml={"output": "x.xml"},
        json={"output": "j.json"},
        lcov={"output": "l.info"},
    )
    assert _coverage.coverage_outputs(["html", "xml", "json", "lcov"], pyproject) == (
        "h",
        ("x.xml", "j.json", "l.info"),
    )


def test_coverage_outputs_reports_win_over_pyproject() -> None:
    pyproject = _coverage_table(html={"directory": "h"}, xml={"output": "x.xml"})
    assert _coverage.coverage_outputs(["html:cov_html", "xml:cov.xml"], pyproject) == (
        "cov_html",
        ("cov.xml",),
    )


def test_coverage_outputs_ignores_the_options_of_a_format_not_requested() -> None:
    pyproject = _coverage_table(xml={"output": "x.xml"})
    assert _coverage.coverage_outputs(["term"], pyproject).files == ()


def test_coverage_outputs_json_and_lcov_defaults() -> None:
    assert _coverage.coverage_outputs(["json", "lcov"], _NO_PYPROJECT).files == (
        "coverage.json",
        "coverage.lcov",
    )


def test_coverage_outputs_keeps_the_order_of_the_reports() -> None:
    assert _coverage.coverage_outputs(["lcov", "xml"], _NO_PYPROJECT).files == (
        "coverage.lcov",
        "coverage.xml",
    )


def test_coverage_outputs_lists_a_file_once() -> None:
    assert _coverage.coverage_outputs(["xml", "xml:coverage.xml"], _NO_PYPROJECT).files == (
        "coverage.xml",
    )


def test_coverage_outputs_html_with_an_empty_argument_uses_pyproject() -> None:
    pyproject = _coverage_table(html={"directory": "h"})
    assert _coverage.coverage_outputs(["html:"], pyproject).html_dir == "h"


def test_coverage_outputs_does_not_modify_the_reports() -> None:
    reports = ["html:cov_html", "xml"]
    _coverage.coverage_outputs(reports, _NO_PYPROJECT)
    assert reports == ["html:cov_html", "xml"]


######################################
#     Tests for _report_argument     #
######################################


@pytest.mark.parametrize(
    ("reports", "expected"),
    [
        (["html:cov"], "cov"),
        (["term", "html:cov"], "cov"),
        (["html"], None),
        (["html:"], None),
        (["xml:cov.xml"], None),
        ([], None),
        (["html:a", "html:b"], "a"),
        (["html:a:b"], "a:b"),
    ],
)
def test_report_argument(reports: list[str], expected: str | None) -> None:
    assert _coverage._report_argument(reports, "html") == expected


######################################
#     Tests for _coverage_option     #
######################################


def test_coverage_option_reads_the_value() -> None:
    pyproject = _coverage_table(xml={"output": "x.xml"})
    assert _coverage._coverage_option("xml", "output", pyproject) == "x.xml"


def test_coverage_option_missing_is_none() -> None:
    assert _coverage._coverage_option("xml", "output", _NO_PYPROJECT) is None


def test_coverage_option_not_a_string_is_none() -> None:
    pyproject = _coverage_table(xml={"output": 3})
    assert _coverage._coverage_option("xml", "output", pyproject) is None
