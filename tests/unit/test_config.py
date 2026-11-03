from __future__ import annotations

import pytest
from invoke.config import Config
from invoke.context import Context

from invoke_tasklib.config import (
    _check_keys,
    _normalize_groups,
    _validate_python_version,
    get_config,
)


def _context(tasklib_config: dict | None = None) -> Context:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return Context(config=Config(overrides=overrides))


def test_get_config_requires_package_name() -> None:
    with pytest.raises(ValueError, match=r"tasklib\.package\.name"):
        get_config(_context())


def test_get_config_defaults() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}}))
    assert cfg == {
        "package": {"name": "mypkg", "python_version": "3.14"},
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
    }


def test_get_config_overrides() -> None:
    cfg = get_config(
        _context(
            {
                "package": {"name": "mypkg", "python_version": "3.11"},
                "paths": {"src": "mypkg", "docs_config": "mkdocs.yml"},
            }
        )
    )
    assert cfg["package"]["python_version"] == "3.11"
    assert cfg["paths"]["src"] == "mypkg"
    assert cfg["paths"]["docs_config"] == "mkdocs.yml"
    assert cfg["paths"]["unit_tests"] == "tests/unit"


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
    assert cfg["paths"] == {
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
    assert cfg["groups"]["install"] == "dev,test"
    assert cfg["groups"]["update"] == "dev,test,docs"


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
    assert get_config(c)["package"]["python_version"] == version


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
    assert get_config(c)["groups"]["install"] == "dev,docs"


def test_get_config_groups_update_as_list() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"update": ["dev", "test"]}})
    assert get_config(c)["groups"]["update"] == "dev,test"


def test_get_config_groups_as_string_is_unchanged() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": "dev,test"}})
    assert get_config(c)["groups"] == {"install": "dev,test", "update": "dev,docs"}


def test_get_config_groups_as_empty_list_installs_no_group() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": []}})
    assert get_config(c)["groups"]["install"] == ""


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
    assert get_config(c)["paths"]["benchmarks"] == "f"


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
