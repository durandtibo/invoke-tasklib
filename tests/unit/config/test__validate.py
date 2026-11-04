from __future__ import annotations

import pytest

from invoke_tasklib.config import COV_REPORTS
from invoke_tasklib.config._validate import (
    _as_mapping,
    _as_names,
    _check_keys,
    _int_from_text,
    _is_cov_report,
    _normalize_groups,
    _validate_bool,
    _validate_check_tasks,
    _validate_cov_fail_under,
    _validate_cov_reports,
    _validate_fix_tasks,
    _validate_import_name,
    _validate_int,
    _validate_python_version,
    _validate_steps,
    _validate_str,
)

#################################
#     Tests for _as_mapping     #
#################################


def test_as_mapping_returns_the_mapping() -> None:
    assert _as_mapping("tasklib.paths", {"src": "x"}) == {"src": "x"}


def test_as_mapping_returns_the_same_object() -> None:
    value = {"src": "x"}
    assert _as_mapping("tasklib.paths", value) is value


def test_as_mapping_accepts_an_empty_mapping() -> None:
    assert _as_mapping("tasklib.paths", {}) == {}


@pytest.mark.parametrize("value", ["foo", "", ["a"], 5, None, True])
def test_as_mapping_rejects_other_types(value: object) -> None:
    with pytest.raises(ValueError, match=r"'tasklib\.paths' must be a mapping, got "):
        _as_mapping("tasklib.paths", value)


##############################################
#     Tests for _validate_python_version     #
##############################################


def test_validate_python_version_returns_valid_string() -> None:
    assert _validate_python_version("3.10") == "3.10"


def test_validate_python_version_accepts_none() -> None:
    assert _validate_python_version(None) is None


def test_validate_python_version_rejects_float() -> None:
    with pytest.raises(ValueError, match=r"got 3\.1\."):
        _validate_python_version(3.1)


###############################
#     Tests for _as_names     #
###############################


def test_as_names_splits_a_comma_separated_string() -> None:
    assert _as_names("tasklib.x.y", "a,b") == ["a", "b"]


def test_as_names_converts_a_list() -> None:
    assert _as_names("tasklib.x.y", ["a", "b"]) == ["a", "b"]


def test_as_names_converts_a_tuple() -> None:
    assert _as_names("tasklib.x.y", ("a", "b")) == ["a", "b"]


def test_as_names_strips_the_names() -> None:
    assert _as_names("tasklib.x.y", " a , b ") == ["a", "b"]


def test_as_names_drops_the_empty_names() -> None:
    assert _as_names("tasklib.x.y", ["a", "", "  ", "b"]) == ["a", "b"]


def test_as_names_removes_the_duplicates_and_keeps_the_order() -> None:
    assert _as_names("tasklib.x.y", "b,a,b,a") == ["b", "a"]


def test_as_names_of_an_empty_string_is_empty() -> None:
    assert _as_names("tasklib.x.y", "") == []


def test_as_names_of_an_empty_list_is_empty() -> None:
    assert _as_names("tasklib.x.y", []) == []


def test_as_names_does_not_mutate_a_list() -> None:
    names = [" a ", "a"]
    _as_names("tasklib.x.y", names)
    assert names == [" a ", "a"]


@pytest.mark.parametrize("value", [3, None, True, {"a": 1}, ["a", 1]])
def test_as_names_rejects_other_values(value: object) -> None:
    with pytest.raises(
        ValueError,
        match=r"'tasklib\.x\.y' must be a comma-separated string or a list of strings",
    ):
        _as_names("tasklib.x.y", value)


#######################################
#     Tests for _normalize_groups     #
#######################################


def test_normalize_groups_converts_a_list() -> None:
    assert _normalize_groups("install", ["dev", "docs"]) == ("dev", "docs")


def test_normalize_groups_splits_a_string() -> None:
    assert _normalize_groups("install", "dev") == ("dev",)


def test_normalize_groups_accepts_tuple() -> None:
    assert _normalize_groups("update", ("dev", "docs")) == ("dev", "docs")


def test_normalize_groups_splits_a_comma_separated_string() -> None:
    assert _normalize_groups("install", "dev,docs") == ("dev", "docs")


def test_normalize_groups_strips_the_names() -> None:
    assert _normalize_groups("install", " dev , docs ") == ("dev", "docs")


def test_normalize_groups_drops_empty_names() -> None:
    assert _normalize_groups("install", "dev,,docs,") == ("dev", "docs")


def test_normalize_groups_of_an_empty_string_is_empty() -> None:
    assert _normalize_groups("install", "") == ()


def test_normalize_groups_removes_the_duplicates() -> None:
    assert _normalize_groups("install", "dev,docs,dev") == ("dev", "docs")


def test_normalize_groups_does_not_mutate_a_list() -> None:
    groups = [" dev "]
    _normalize_groups("install", groups)
    assert groups == [" dev "]


def test_normalize_groups_error_names_the_key() -> None:
    with pytest.raises(ValueError, match=r"'tasklib\.groups\.update'"):
        _normalize_groups("update", 3)


#################################
#     Tests for _check_keys     #
#################################


def test_check_keys_accepts_known_keys() -> None:
    assert _check_keys("paths", {"src": "x"}, ["src", "tests"]) is None


def test_check_keys_accepts_empty_section() -> None:
    assert _check_keys("paths", {}, ["src", "tests"]) is None


def test_check_keys_lists_valid_keys_sorted() -> None:
    with pytest.raises(ValueError, match=r"Valid keys: src, tests$"):
        _check_keys("paths", {"zzz": "x"}, ["tests", "src"])


def test_check_keys_without_close_match_has_no_hint() -> None:
    with pytest.raises(ValueError, match=r"^Unknown key 'zzz' in 'tasklib\.paths'\. Valid"):
        _check_keys("paths", {"zzz": "x"}, ["src", "tests"])


def test_check_keys_reports_all_unknown_keys() -> None:
    with pytest.raises(ValueError, match=r"Unknown keys 'aaa', 'zzz' in"):
        _check_keys("paths", {"zzz": 1, "aaa": 2}, ["src", "tests"])


def test_check_keys_suggests_closest_key() -> None:
    with pytest.raises(ValueError, match=r"\(did you mean 'tests'\?\)"):
        _check_keys("paths", {"test": "x"}, ["src", "tests"])


###################################
#     Tests for _validate_int     #
###################################


def test_validate_int_accepts_the_minimum() -> None:
    assert _validate_int("test", "unit_timeout", 1, minimum=1) == 1


def test_validate_int_names_the_section_in_the_error() -> None:
    with pytest.raises(ValueError, match=r"'tasklib\.paths\.depth' must be an integer >= 1"):
        _validate_int("paths", "depth", 0, minimum=1)


def test_validate_int_rejects_below_the_minimum() -> None:
    with pytest.raises(ValueError, match=r"must be an integer >= 1, got 0"):
        _validate_int("test", "unit_timeout", 0, minimum=1)


def test_validate_int_converts_a_string_of_digits() -> None:
    assert _validate_int("test", "unit_timeout", "30", minimum=1) == 30


def test_validate_int_rejects_a_string_below_the_minimum() -> None:
    with pytest.raises(ValueError, match=r"must be an integer >= 1, got '0'"):
        _validate_int("test", "unit_timeout", "0", minimum=1)


@pytest.mark.parametrize("value", [True, 1.5, "ten", "1.5", "", None])
def test_validate_int_rejects_non_integers(value: object) -> None:
    with pytest.raises(ValueError, match=r"'tasklib.test.unit_timeout' must be an integer"):
        _validate_int("test", "unit_timeout", value, minimum=0)


####################################
#     Tests for _validate_bool     #
####################################


@pytest.mark.parametrize("value", [True, False])
def test_validate_bool_accepts_booleans(value: bool) -> None:
    assert _validate_bool("test", "xdoctest", value) is value


@pytest.mark.parametrize("value", ["true", "TRUE", "True", "1", "yes", "Yes", "on", "ON"])
def test_validate_bool_accepts_the_true_spellings(value: str) -> None:
    assert _validate_bool("test", "xdoctest", value) is True


@pytest.mark.parametrize("value", ["false", "FALSE", "False", "0", "no", "No", "off", "OFF"])
def test_validate_bool_accepts_the_false_spellings(value: str) -> None:
    assert _validate_bool("test", "xdoctest", value) is False


def test_validate_bool_names_the_section_in_the_error() -> None:
    with pytest.raises(ValueError, match=r"'tasklib\.check\.keep_going' must be a boolean"):
        _validate_bool("check", "keep_going", "maybe")


@pytest.mark.parametrize("value", [1, 0, "maybe", "", None])
def test_validate_bool_rejects_non_booleans(value: object) -> None:
    with pytest.raises(ValueError, match=r"'tasklib.test.xdoctest' must be a boolean"):
        _validate_bool("test", "xdoctest", value)


###########################################
#     Tests for _validate_import_name     #
###########################################


@pytest.mark.parametrize("value", ["mypkg", "my_pkg", "ns.mypkg"])
def test_validate_import_name_accepts_module_names(value: str) -> None:
    assert _validate_import_name(value) == value


@pytest.mark.parametrize("value", ["my-pkg", "", "1pkg", "a..b", "my pkg", 3, None])
def test_validate_import_name_rejects_invalid_names(value: object) -> None:
    with pytest.raises(ValueError, match=r"must be a Python module name"):
        _validate_import_name(value)


####################################
#     Tests for _int_from_text     #
####################################


def test_int_from_text_converts_digits() -> None:
    assert _int_from_text("90") == 90


@pytest.mark.parametrize("value", [90, None, True, "9.5", "-1", "", " 90", "ninety", "٩٠", ["90"]])
def test_int_from_text_keeps_other_values(value: object) -> None:
    assert _int_from_text(value) == value


###################################
#     Tests for _validate_str     #
###################################


def test_validate_str_returns_a_non_empty_string() -> None:
    assert _validate_str("paths", "src", "src/mypkg") == "src/mypkg"


@pytest.mark.parametrize("value", ["", 5, None, ["a"], True])
def test_validate_str_rejects_other_values(value: object) -> None:
    with pytest.raises(ValueError, match=r"'tasklib\.paths\.src' must be a non-empty string, got "):
        _validate_str("paths", "src", value)


def test_validate_str_error_names_the_section_and_the_key() -> None:
    with pytest.raises(ValueError, match=r"'tasklib\.package\.name' must be"):
        _validate_str("package", "name", "")


##################################################
#     Tests for _validate_int with a maximum     #
##################################################


def test_validate_int_accepts_the_maximum() -> None:
    assert _validate_int("test", "cov_fail_under", 100, minimum=0, maximum=100) == 100


def test_validate_int_rejects_above_the_maximum() -> None:
    with pytest.raises(ValueError, match=r"must be an integer between 0 and 100, got 101"):
        _validate_int("test", "cov_fail_under", 101, minimum=0, maximum=100)


def test_validate_int_without_maximum_has_no_upper_limit() -> None:
    assert _validate_int("test", "unit_timeout", 10**9, minimum=1) == 10**9


###########################################
#     Tests for _validate_cov_reports     #
###########################################


def test_validate_cov_reports_comma_separated_string() -> None:
    assert _validate_cov_reports("html,xml,term") == ("html", "xml", "term")


def test_validate_cov_reports_list() -> None:
    assert _validate_cov_reports(["term-missing", "lcov"]) == ("term-missing", "lcov")


def test_validate_cov_reports_tuple() -> None:
    assert _validate_cov_reports(("json",)) == ("json",)


def test_validate_cov_reports_strips_spaces() -> None:
    assert _validate_cov_reports(" html , xml ") == ("html", "xml")


def test_validate_cov_reports_removes_duplicates_and_keeps_the_order() -> None:
    assert _validate_cov_reports("xml,html,xml") == ("xml", "html")


@pytest.mark.parametrize("value", ["", ",", " ", []])
def test_validate_cov_reports_empty_means_no_report_option(value: object) -> None:
    assert _validate_cov_reports(value) == ()


@pytest.mark.parametrize("report", sorted(COV_REPORTS))
def test_validate_cov_reports_accepts_every_known_report(report: str) -> None:
    assert _validate_cov_reports(report) == (report,)


def test_validate_cov_reports_rejects_an_unknown_report() -> None:
    with pytest.raises(ValueError, match=r"Unknown coverage report \['htlm'\]"):
        _validate_cov_reports("html,htlm")


def test_validate_cov_reports_error_lists_the_valid_reports() -> None:
    with pytest.raises(
        ValueError, match=r"Valid reports: annotate, html, json, lcov, term, term-missing, xml"
    ):
        _validate_cov_reports("nope")


@pytest.mark.parametrize("value", [5, None, True, ["html", 5], {"html": 1}])
def test_validate_cov_reports_rejects_other_types(value: object) -> None:
    with pytest.raises(ValueError, match=r"'tasklib.test.cov_reports' must be a comma-separated"):
        _validate_cov_reports(value)


###########################################
#     Tests for _validate_check_tasks     #
###########################################


def test_validate_check_tasks_comma_separated_string() -> None:
    assert _validate_check_tasks("lint, unit") == ("lint", "unit")


def test_validate_check_tasks_list() -> None:
    assert _validate_check_tasks(["types", "docs"]) == ("types", "docs")


def test_validate_check_tasks_removes_duplicates_keeping_the_order() -> None:
    assert _validate_check_tasks("unit,lint,unit") == ("unit", "lint")


def test_validate_check_tasks_ignores_empty_names() -> None:
    assert _validate_check_tasks("lint,,") == ("lint",)


def test_validate_check_tasks_rejects_an_empty_value() -> None:
    with pytest.raises(ValueError, match=r"must contain at least one step"):
        _validate_check_tasks("")


def test_validate_check_tasks_rejects_an_unknown_step() -> None:
    with pytest.raises(ValueError, match=r"Unknown check step \['lnt'\] in 'tasklib.check.tasks'"):
        _validate_check_tasks("lnt")


def test_validate_check_tasks_lists_the_valid_steps() -> None:
    with pytest.raises(ValueError, match=r"Valid steps: format-python, format-docstrings, lint"):
        _validate_check_tasks("lnt")


@pytest.mark.parametrize("value", [3, None, ["lint", 3]])
def test_validate_check_tasks_rejects_a_wrong_type(value: object) -> None:
    with pytest.raises(ValueError, match=r"must be a comma-separated string or a list"):
        _validate_check_tasks(value)


#########################################
#     Tests for _validate_fix_tasks     #
#########################################


def test_validate_fix_tasks_comma_separated_string() -> None:
    assert _validate_fix_tasks("lint, format-python") == ("lint", "format-python")


def test_validate_fix_tasks_list() -> None:
    assert _validate_fix_tasks(["shell", "lint"]) == ("shell", "lint")


def test_validate_fix_tasks_removes_duplicates_keeping_the_order() -> None:
    assert _validate_fix_tasks("shell,lint,shell") == ("shell", "lint")


def test_validate_fix_tasks_rejects_an_empty_value() -> None:
    with pytest.raises(ValueError, match=r"'tasklib\.fix\.tasks' must contain at least one step"):
        _validate_fix_tasks("")


def test_validate_fix_tasks_rejects_an_unknown_step() -> None:
    with pytest.raises(ValueError, match=r"Unknown fix step \['lnt'\] in 'tasklib.fix.tasks'"):
        _validate_fix_tasks("lnt")


def test_validate_fix_tasks_rejects_a_check_only_step() -> None:
    with pytest.raises(ValueError, match=r"Unknown fix step \['types'\]"):
        _validate_fix_tasks("types")


def test_validate_fix_tasks_lists_the_valid_steps() -> None:
    with pytest.raises(
        ValueError, match=r"Valid steps: lint, format-python, format-docstrings, shell"
    ):
        _validate_fix_tasks("lnt")


@pytest.mark.parametrize("value", [3, None, ["lint", 3]])
def test_validate_fix_tasks_rejects_a_wrong_type(value: object) -> None:
    with pytest.raises(ValueError, match=r"'tasklib\.fix\.tasks' must be a comma-separated"):
        _validate_fix_tasks(value)


#####################################
#     Tests for _validate_steps     #
#####################################


def test_validate_steps_accepts_the_valid_steps() -> None:
    assert _validate_steps("fix", "fix", ("a", "b"), "b,a") == ("b", "a")


def test_validate_steps_names_the_section_and_the_noun() -> None:
    with pytest.raises(ValueError, match=r"Unknown thing step \['c'\] in 'tasklib.sec.tasks'"):
        _validate_steps("sec", "thing", ("a", "b"), "c")


##########################################
#     Tests for _validate_cov_fail_under #
##########################################


def test_validate_cov_fail_under_none_is_not_set() -> None:
    assert _validate_cov_fail_under(None) is None


@pytest.mark.parametrize(("value", "expected"), [(0, 0), (90, 90), (100, 100), ("85", 85)])
def test_validate_cov_fail_under_accepts_a_percentage(value: object, expected: int) -> None:
    assert _validate_cov_fail_under(value) == expected


@pytest.mark.parametrize("value", [-1, 101, 1.5, "ninety", True])
def test_validate_cov_fail_under_rejects_an_invalid_value(value: object) -> None:
    with pytest.raises(ValueError, match=r"'tasklib.test.cov_fail_under' must be an integer"):
        _validate_cov_fail_under(value)


@pytest.mark.parametrize(
    "value",
    [
        "term-missing:skip-covered",
        "html:cov_html",
        "xml:reports/coverage.xml",
        "json:cov.json",
        "lcov:cov.info",
        "annotate:notes",
        "html:C:/cov",
    ],
)
def test_validate_cov_reports_accepts_an_argument(value: str) -> None:
    assert _validate_cov_reports(value) == (value,)


def test_validate_cov_reports_keeps_the_arguments_in_a_list() -> None:
    value = ["term-missing:skip-covered", "html:cov_html", "xml"]
    assert _validate_cov_reports(value) == ("term-missing:skip-covered", "html:cov_html", "xml")


def test_validate_cov_reports_keeps_two_arguments_of_a_format() -> None:
    assert _validate_cov_reports("html:a,html:b") == ("html:a", "html:b")


@pytest.mark.parametrize("value", ["html:", "term-missing:", ":skip-covered", ":"])
def test_validate_cov_reports_rejects_an_empty_part(value: str) -> None:
    with pytest.raises(ValueError, match=r"Unknown coverage report"):
        _validate_cov_reports(value)


def test_validate_cov_reports_rejects_an_unknown_format_with_an_argument() -> None:
    with pytest.raises(ValueError, match=r"Unknown coverage report \['htlm:dir'\]"):
        _validate_cov_reports("htlm:dir")


@pytest.mark.parametrize("value", ["HTML", "term_missing", "html/", "html cov"])
def test_validate_cov_reports_rejects_a_misspelled_format(value: str) -> None:
    with pytest.raises(ValueError, match=r"Unknown coverage report"):
        _validate_cov_reports(value)


####################################
#     Tests for _is_cov_report     #
####################################


@pytest.mark.parametrize("report", sorted(COV_REPORTS))
def test_is_cov_report_accepts_a_format(report: str) -> None:
    assert _is_cov_report(report) is True


@pytest.mark.parametrize("name", ["html:dir", "term-missing:skip-covered", "xml:a:b"])
def test_is_cov_report_accepts_a_format_with_an_argument(name: str) -> None:
    assert _is_cov_report(name) is True


@pytest.mark.parametrize("name", ["", "nope", "html:", ":dir", "nope:dir"])
def test_is_cov_report_rejects_other_values(name: str) -> None:
    assert _is_cov_report(name) is False
