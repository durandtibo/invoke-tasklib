from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest
from invoke.config import Config
from invoke.context import Context
from invoke.exceptions import Exit

from invoke_tasklib.config import (
    COV_REPORTS,
    DEFAULT_GROUPS,
    DEFAULT_PACKAGE,
    DEFAULT_PATHS,
    DEFAULT_TEST,
    _as_mapping,
    _check_keys,
    _default_src,
    _int_from_text,
    _normalize_groups,
    _validate_bool,
    _validate_cov_reports,
    _validate_import_name,
    _validate_int,
    _validate_python_version,
    _validate_str,
    default_config,
    get_config,
    load_config,
)

if TYPE_CHECKING:
    from pathlib import Path


def _context(tasklib_config: object = None) -> Context:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return Context(config=Config(overrides=overrides))


def test_get_config_requires_package_name() -> None:
    with pytest.raises(ValueError, match=r"tasklib\.package\.name"):
        get_config(_context())


def test_get_config_defaults() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}}))
    assert asdict(cfg) == {
        "package": {"name": "mypkg", "import_name": "mypkg", "python_version": "3.14"},
        "paths": {
            "src": "src/mypkg",
            "tests": "tests",
            "unit_tests": "tests/unit",
            "integration_tests": "tests/integration",
            "functional_tests": "tests/functional",
            "benchmarks": "tests/benchmarks",
            "docs_config": "docs/mkdocs.yml",
        },
        "groups": {"install": "dev", "update": "dev,docs"},
        "test": {
            "unit_timeout": 10,
            "integration_timeout": 60,
            "functional_timeout": 60,
            "xdoctest": True,
            "cov_fail_under": None,
            "cov_reports": ("html", "xml", "term"),
        },
    }


def test_get_config_test_overrides() -> None:
    cfg = get_config(
        _context(
            {
                "package": {"name": "mypkg"},
                "test": {
                    "unit_timeout": 5,
                    "integration_timeout": 120,
                    "functional_timeout": 300,
                    "xdoctest": False,
                    "cov_fail_under": 90,
                    "cov_reports": ["xml"],
                },
            }
        )
    )
    assert asdict(cfg.test) == {
        "unit_timeout": 5,
        "integration_timeout": 120,
        "functional_timeout": 300,
        "xdoctest": False,
        "cov_fail_under": 90,
        "cov_reports": ("xml",),
    }


def test_get_config_test_partial_override_keeps_other_defaults() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}, "test": {"unit_timeout": 5}}))
    assert cfg.test.integration_timeout == 60


def test_get_config_test_unknown_key() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"unit_timout": 5}})
    with pytest.raises(
        ValueError,
        match=r"Unknown key 'unit_timout' \(did you mean 'unit_timeout'\?\) in 'tasklib.test'",
    ):
        get_config(c)


def test_get_config_test_invalid_timeout() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"unit_timeout": 0}})
    with pytest.raises(ValueError, match=r"'tasklib.test.unit_timeout' must be an integer >= 1"):
        get_config(c)


def test_get_config_test_invalid_xdoctest() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"xdoctest": "no"}})
    with pytest.raises(ValueError, match=r"'tasklib.test.xdoctest' must be a boolean"):
        get_config(c)


@pytest.mark.parametrize("value", [-1, 101, 1000])
def test_get_config_test_invalid_cov_fail_under(value: int) -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_fail_under": value}})
    with pytest.raises(
        ValueError,
        match=r"'tasklib.test.cov_fail_under' must be an integer between 0 and 100",
    ):
        get_config(c)


@pytest.mark.parametrize("value", [0, 100])
def test_get_config_test_cov_fail_under_bounds_are_valid(value: int) -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_fail_under": value}})
    assert get_config(c).test.cov_fail_under == value


def test_get_config_import_name_replaces_hyphens() -> None:
    cfg = get_config(_context({"package": {"name": "my-pkg"}}))
    assert cfg.package.import_name == "my_pkg"


def test_get_config_import_name_override() -> None:
    cfg = get_config(_context({"package": {"name": "my-pkg", "import_name": "other"}}))
    assert cfg.package.import_name == "other"


def test_get_config_src_uses_the_import_name() -> None:
    cfg = get_config(_context({"package": {"name": "my-pkg"}}))
    assert cfg.paths.src == "src/my_pkg"


def test_get_config_explicit_src_wins_over_import_name() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}, "paths": {"src": "lib"}}))
    assert cfg.paths.src == "lib"


def test_get_config_invalid_import_name() -> None:
    c = _context({"package": {"name": "mypkg", "import_name": "my-pkg"}})
    with pytest.raises(ValueError, match=r"'tasklib.package.import_name' must be a Python module"):
        get_config(c)


@pytest.mark.parametrize(
    "key",
    [
        "src",
        "tests",
        "unit_tests",
        "integration_tests",
        "functional_tests",
        "benchmarks",
        "docs_config",
    ],
)
def test_get_config_rejects_an_empty_path(key: str) -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {key: ""}})
    with pytest.raises(ValueError, match=rf"'tasklib\.paths\.{key}' must be a non-empty string"):
        get_config(c)


@pytest.mark.parametrize("value", [5, ["src"], True, 1.5])
def test_get_config_rejects_a_path_that_is_not_a_string(value: object) -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"tests": value}})
    with pytest.raises(ValueError, match=r"'tasklib\.paths\.tests' must be a non-empty string"):
        get_config(c)


@pytest.mark.parametrize("value", [["a"], 5, True])
def test_get_config_rejects_a_package_name_that_is_not_a_string(value: object) -> None:
    c = _context({"package": {"name": value}})
    with pytest.raises(ValueError, match=r"'tasklib\.package\.name' must be a non-empty string"):
        get_config(c)


def test_get_config_rejects_an_unknown_top_level_key() -> None:
    c = _context({"package": {"name": "mypkg"}, "path": {"src": "x"}})
    with pytest.raises(
        ValueError, match=r"Unknown key 'path' \(did you mean 'paths'\?\) in 'tasklib'"
    ):
        get_config(c)


def test_get_config_top_level_error_lists_the_valid_sections() -> None:
    c = _context({"package": {"name": "mypkg"}, "zzz": {}})
    with pytest.raises(ValueError, match=r"Valid keys: groups, package, paths, test"):
        get_config(c)


def test_get_config_a_missing_name_is_still_reported_as_unset() -> None:
    with pytest.raises(ValueError, match=r"'tasklib\.package\.name' must be set"):
        get_config(_context({"package": {"name": ""}}))


def test_get_config_overrides() -> None:
    cfg = get_config(
        _context(
            {
                "package": {"name": "mypkg", "python_version": "3.11"},
                "paths": {"src": "mypkg", "docs_config": "mkdocs.yml"},
            }
        )
    )
    assert cfg.package.python_version == "3.11"
    assert cfg.paths.src == "mypkg"
    assert cfg.paths.docs_config == "mkdocs.yml"
    assert cfg.paths.unit_tests == "tests/unit"


def test_get_config_all_paths_overridden() -> None:
    cfg = get_config(
        _context(
            {
                "package": {"name": "mypkg"},
                "paths": {
                    "src": "mypkg",
                    "unit_tests": "tests/u",
                    "integration_tests": "tests/i",
                    "functional_tests": "tests/f",
                    "benchmarks": "tests/b",
                },
            }
        )
    )
    assert asdict(cfg.paths) == {
        "src": "mypkg",
        "tests": "tests",
        "unit_tests": "tests/u",
        "integration_tests": "tests/i",
        "functional_tests": "tests/f",
        "benchmarks": "tests/b",
        "docs_config": "docs/mkdocs.yml",
    }


def test_get_config_groups_overrides() -> None:
    cfg = get_config(
        _context(
            {
                "package": {"name": "mypkg"},
                "groups": {"install": "dev,test", "update": "dev,test,docs"},
            }
        )
    )
    assert cfg.groups.install == "dev,test"
    assert cfg.groups.update == "dev,test,docs"


########################################
#     Tests for mapping validation     #
########################################


@pytest.mark.parametrize("section", ["package", "paths", "groups", "test"])
def test_get_config_rejects_a_section_that_is_a_string(section: str) -> None:
    c = _context({"package": {"name": "mypkg"}, section: "foo"})
    with pytest.raises(ValueError, match=rf"'tasklib\.{section}' must be a mapping, got 'foo'"):
        get_config(c)


def test_get_config_rejects_a_section_that_is_a_list() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": ["src"]})
    with pytest.raises(ValueError, match=r"'tasklib\.paths' must be a mapping, got \['src'\]"):
        get_config(c)


def test_get_config_rejects_an_empty_section() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": None})
    with pytest.raises(ValueError, match=r"'tasklib\.paths' must be a mapping, got None"):
        get_config(c)


def test_get_config_rejects_a_tasklib_section_that_is_a_string() -> None:
    c = _context("foo")
    with pytest.raises(ValueError, match=r"'tasklib' must be a mapping, got 'foo'"):
        get_config(c)


def test_load_config_exits_on_a_section_that_is_a_string() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": "foo"})
    with pytest.raises(Exit, match=r"'tasklib\.paths' must be a mapping"):
        load_config(c)


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


###############################################
#     Tests for python_version validation     #
###############################################


@pytest.mark.parametrize("version", [3.1, 3.14, 3, True, None, ["3.10"]])
def test_get_config_rejects_non_string_python_version(version: object) -> None:
    c = _context({"package": {"name": "mypkg", "python_version": version}})
    with pytest.raises(ValueError, match=r"must be a string like"):
        get_config(c)


def test_get_config_python_version_error_mentions_quoting() -> None:
    c = _context({"package": {"name": "mypkg", "python_version": 3.1}})
    with pytest.raises(ValueError, match=r"Quote the value in invoke\.yaml"):
        get_config(c)


@pytest.mark.parametrize("version", ["3", "3.", "py3.10", "3.10-dev", "3.x", " 3.10", ""])
def test_get_config_rejects_malformed_python_version(version: str) -> None:
    c = _context({"package": {"name": "mypkg", "python_version": version}})
    with pytest.raises(ValueError, match=r"must be a string like"):
        get_config(c)


@pytest.mark.parametrize("version", ["3.10", "3.9", "3.10.4", "3.14"])
def test_get_config_accepts_quoted_python_version(version: str) -> None:
    c = _context({"package": {"name": "mypkg", "python_version": version}})
    assert get_config(c).package.python_version == version


##############################################
#     Tests for _validate_python_version     #
##############################################


def test_validate_python_version_returns_valid_string() -> None:
    assert _validate_python_version("3.10") == "3.10"


def test_validate_python_version_rejects_float() -> None:
    with pytest.raises(ValueError, match=r"got 3\.1\."):
        _validate_python_version(3.1)


######################################
#     Tests for groups as a list     #
######################################


def test_get_config_groups_install_as_list() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": ["dev", "docs"]}})
    assert get_config(c).groups.install == "dev,docs"


def test_get_config_groups_update_as_list() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"update": ["dev", "test"]}})
    assert get_config(c).groups.update == "dev,test"


def test_get_config_groups_as_string_is_unchanged() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": "dev,test"}})
    assert asdict(get_config(c).groups) == {"install": "dev,test", "update": "dev,docs"}


def test_get_config_groups_as_empty_list_installs_no_group() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": []}})
    assert get_config(c).groups.install == ""


@pytest.mark.parametrize("value", [1, None, ["dev", 1], {"dev": True}])
def test_get_config_rejects_invalid_groups(value: object) -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": value}})
    with pytest.raises(ValueError, match=r"'tasklib\.groups\.install' must be a comma-separated"):
        get_config(c)


#######################################
#     Tests for _normalize_groups     #
#######################################


def test_normalize_groups_joins_list() -> None:
    assert _normalize_groups("install", ["dev", "docs"]) == "dev,docs"


def test_normalize_groups_keeps_string() -> None:
    assert _normalize_groups("install", "dev") == "dev"


def test_normalize_groups_accepts_tuple() -> None:
    assert _normalize_groups("update", ("dev", "docs")) == "dev,docs"


def test_normalize_groups_error_names_the_key() -> None:
    with pytest.raises(ValueError, match=r"'tasklib\.groups\.update'"):
        _normalize_groups("update", 3)


##################################
#     Tests for unknown keys     #
##################################


def test_get_config_rejects_unknown_paths_key() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"unit_test": "x"}})
    with pytest.raises(
        ValueError, match=r"Unknown key 'unit_test' \(did you mean 'unit_tests'\?\)"
    ):
        get_config(c)


def test_get_config_rejects_unknown_package_key() -> None:
    c = _context({"package": {"name": "mypkg", "python_versoin": "3.11"}})
    with pytest.raises(
        ValueError, match=r"Unknown key 'python_versoin' \(did you mean 'python_version'"
    ):
        get_config(c)


_MISSPELLED_INSTALL = "instal"  # codespell:ignore instal


def test_get_config_rejects_unknown_groups_key() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {_MISSPELLED_INSTALL: "dev"}})
    with pytest.raises(
        ValueError, match=rf"Unknown key '{_MISSPELLED_INSTALL}' \(did you mean 'install'"
    ):
        get_config(c)


def test_get_config_error_names_the_section() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"nope": "x"}})
    with pytest.raises(ValueError, match=r"in 'tasklib\.paths'"):
        get_config(c)


def test_get_config_accepts_every_known_key() -> None:
    c = _context(
        {
            "package": {"name": "mypkg", "python_version": "3.11"},
            "paths": {
                "src": "a",
                "tests": "b",
                "unit_tests": "c",
                "integration_tests": "d",
                "functional_tests": "e",
                "benchmarks": "f",
                "docs_config": "g",
            },
            "groups": {"install": "dev", "update": "dev"},
        }
    )
    assert get_config(c).paths.benchmarks == "f"


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


#################################
#     Tests for load_config     #
#################################


def test_load_config_returns_the_resolved_config() -> None:
    c = Context(config=Config(overrides={"tasklib": {"package": {"name": "mypkg"}}}))
    assert load_config(c) == get_config(c)


def test_load_config_exits_on_missing_package_name() -> None:
    with pytest.raises(Exit, match=r"'tasklib.package.name' must be set"):
        load_config(Context(config=Config()))


def test_load_config_exit_code_is_2() -> None:
    with pytest.raises(Exit) as excinfo:
        load_config(Context(config=Config()))
    assert excinfo.value.code == 2


def test_load_config_exits_on_unknown_key() -> None:
    c = Context(config=Config(overrides={"tasklib": {"paths": {"sr": "x"}}}))
    with pytest.raises(Exit, match=r"Unknown key 'sr'"):
        load_config(c)


###################################
#     Tests for _validate_int     #
###################################


def test_validate_int_accepts_the_minimum() -> None:
    assert _validate_int("unit_timeout", 1, minimum=1) == 1


def test_validate_int_rejects_below_the_minimum() -> None:
    with pytest.raises(ValueError, match=r"must be an integer >= 1, got 0"):
        _validate_int("unit_timeout", 0, minimum=1)


@pytest.mark.parametrize("value", [True, 1.5, "10", None])
def test_validate_int_rejects_non_integers(value: object) -> None:
    with pytest.raises(ValueError, match=r"'tasklib.test.unit_timeout' must be an integer"):
        _validate_int("unit_timeout", value, minimum=0)


####################################
#     Tests for _validate_bool     #
####################################


@pytest.mark.parametrize("value", [True, False])
def test_validate_bool_accepts_booleans(value: bool) -> None:
    assert _validate_bool("xdoctest", value) is value


@pytest.mark.parametrize("value", [1, 0, "true", None])
def test_validate_bool_rejects_non_booleans(value: object) -> None:
    with pytest.raises(ValueError, match=r"'tasklib.test.xdoctest' must be a boolean"):
        _validate_bool("xdoctest", value)


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


##################################
#     Tests for _default_src     #
##################################


def test_default_src_prefers_the_src_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src" / "mypkg").mkdir(parents=True)
    (tmp_path / "mypkg").mkdir()
    assert _default_src("mypkg") == "src/mypkg"


def test_default_src_uses_the_flat_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mypkg").mkdir()
    assert _default_src("mypkg") == "mypkg"


def test_default_src_falls_back_to_the_src_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert _default_src("mypkg") == "src/mypkg"


####################################
#     Tests for default_config     #
####################################


def test_default_config_has_the_four_sections() -> None:
    assert sorted(default_config()) == ["groups", "package", "paths", "test"]


def test_default_config_is_the_defaults() -> None:
    assert default_config() == {
        "package": DEFAULT_PACKAGE,
        "paths": DEFAULT_PATHS,
        "groups": DEFAULT_GROUPS,
        "test": DEFAULT_TEST,
    }


def test_default_config_returns_new_dicts() -> None:
    default_config()["paths"]["src"] = "changed"
    assert DEFAULT_PATHS["src"] is None


def test_default_config_is_deterministic() -> None:
    assert default_config() == default_config()


####################################
#     Tests for _int_from_text     #
####################################


def test_int_from_text_converts_digits() -> None:
    assert _int_from_text("90") == 90


@pytest.mark.parametrize("value", [90, None, True, "9.5", "-1", "", " 90", "ninety", "٩٠", ["90"]])
def test_int_from_text_keeps_other_values(value: object) -> None:
    assert _int_from_text(value) == value


def test_get_config_accepts_cov_fail_under_given_as_text() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_fail_under": "90"}})
    assert get_config(c).test.cov_fail_under == 90


def test_get_config_rejects_cov_fail_under_that_is_not_a_number_text() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_fail_under": "high"}})
    with pytest.raises(ValueError, match=r"'tasklib.test.cov_fail_under' must be an integer"):
        get_config(c)


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
    assert _validate_int("cov_fail_under", 100, minimum=0, maximum=100) == 100


def test_validate_int_rejects_above_the_maximum() -> None:
    with pytest.raises(ValueError, match=r"must be an integer between 0 and 100, got 101"):
        _validate_int("cov_fail_under", 101, minimum=0, maximum=100)


def test_validate_int_without_maximum_has_no_upper_limit() -> None:
    assert _validate_int("unit_timeout", 10**9, minimum=1) == 10**9


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


def test_get_config_cov_reports_error_is_reported() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_reports": "nope"}})
    with pytest.raises(ValueError, match=r"Unknown coverage report \['nope'\]"):
        get_config(c)
