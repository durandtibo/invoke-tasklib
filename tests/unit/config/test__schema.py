from __future__ import annotations

import json
import re
from dataclasses import fields

import pytest

from invoke_tasklib import config as config_module
from invoke_tasklib.config import (
    SCHEMA,
    CheckConfig,
    GroupsConfig,
    PackageConfig,
    PathsConfig,
    default_config,
    json_schema,
)
from invoke_tasklib.config._schema import Unset, _defaults, _path, _timeout

####################################
#     Tests for default_config     #
####################################


def test_default_config_whole_output() -> None:
    # Every key is an ``Unset``, which equals "".
    assert default_config() == {
        "package": {"name": "", "import_name": "", "python_version": ""},
        "paths": {
            "src": "",
            "tests": "",
            "unit_tests": "",
            "integration_tests": "",
            "functional_tests": "",
            "benchmarks": "",
            "docs_config": "",
        },
        "groups": {"install": "", "update": ""},
        "test": {
            "unit_timeout": "",
            "integration_timeout": "",
            "functional_timeout": "",
            "xdoctest": "",
            "timeout": "",
            "cov_fail_under": "",
            "cov_reports": "",
        },
        "types": {"checker": ""},
        "check": {"tasks": "", "cov": ""},
        "fix": {"tasks": ""},
    }


def test_default_config_has_the_seven_sections() -> None:
    assert sorted(default_config()) == [
        "check",
        "fix",
        "groups",
        "package",
        "paths",
        "test",
        "types",
    ]


@pytest.mark.parametrize(
    ("section", "key"),
    [
        ("package", "name"),
        ("paths", "tests"),
        ("groups", "install"),
        ("test", "xdoctest"),
        ("test", "unit_timeout"),
        ("test", "cov_fail_under"),
        ("types", "checker"),
    ],
)
def test_default_config_registers_a_placeholder(section: str, key: str) -> None:
    assert isinstance(default_config()[section][key], Unset)


def test_default_config_has_the_keys_of_the_schema() -> None:
    assert {s: list(keys) for s, keys in default_config().items()} == {
        s: list(options) for s, options in SCHEMA.items()
    }


def test_default_config_does_not_change_the_schema_defaults() -> None:
    default_config()
    assert SCHEMA["test"]["xdoctest"].default is True


def test_default_config_returns_new_dicts() -> None:
    default_config()["paths"]["src"] = "changed"
    assert SCHEMA["paths"]["src"].default is None


def test_default_config_is_deterministic() -> None:
    assert default_config() == default_config()


#############################
#     Tests for SCHEMA      #
#############################

_SECTION_CLASSES = {
    "package": PackageConfig,
    "paths": PathsConfig,
    "groups": GroupsConfig,
    "test": config_module.TestConfig,
    "check": CheckConfig,
}


def test_schema_sections() -> None:
    assert list(SCHEMA) == ["package", "paths", "groups", "test", "types", "check", "fix"]


@pytest.mark.parametrize("section", sorted(_SECTION_CLASSES))
def test_schema_keys_are_the_fields_of_the_section_dataclass(section: str) -> None:
    assert list(SCHEMA[section]) == [f.name for f in fields(_SECTION_CLASSES[section])]


_OPTIONS = [(s, k) for s, options in SCHEMA.items() for k in options]


_OPTIONS_WITH_DEFAULT = [(s, k) for s, k in _OPTIONS if SCHEMA[s][k].default is not None]


@pytest.mark.parametrize(("section", "key"), _OPTIONS_WITH_DEFAULT)
def test_schema_default_is_valid(section: str, key: str) -> None:
    option = SCHEMA[section][key]
    assert option.validate(f"tasklib.{section}.{key}", option.default) is not None


@pytest.mark.parametrize(("section", "key"), _OPTIONS)
def test_schema_option_has_a_description(section: str, key: str) -> None:
    assert SCHEMA[section][key].doc.endswith((".", ")"))


@pytest.mark.parametrize(("section", "key"), _OPTIONS)
def test_schema_option_has_a_json_type(section: str, key: str) -> None:
    schema = SCHEMA[section][key].json_schema
    assert "type" in schema or "anyOf" in schema or "enum" in schema


@pytest.mark.parametrize(("section", "key"), _OPTIONS)
def test_schema_option_validation_error_names_the_key(section: str, key: str) -> None:
    with pytest.raises(ValueError, match=rf"tasklib\.{section}\.{key}"):
        SCHEMA[section][key].validate(f"tasklib.{section}.{key}", object())


def test_defaults_of_a_section() -> None:
    assert _defaults("check") == {"tasks": None, "cov": False}


def test_defaults_returns_a_new_dict() -> None:
    _defaults("groups")["install"] = "changed"
    assert _defaults("groups")["install"] == ("dev",)


def test_timeout_option() -> None:
    option = _timeout(10, "Timeout.")
    assert (option.default, option.json_schema) == (10, {"type": "integer", "minimum": 1})


def test_timeout_option_rejects_zero() -> None:
    with pytest.raises(ValueError, match=r"'tasklib.test.unit_timeout' must be an integer >= 1"):
        _timeout(10, "Timeout.").validate("tasklib.test.unit_timeout", 0)


def test_path_option() -> None:
    option = _path(None, "Source.")
    assert (option.default, option.doc) == (None, "Source.")


def test_path_option_rejects_an_empty_string() -> None:
    with pytest.raises(ValueError, match=r"'tasklib.paths.src' must be a non-empty string"):
        _path(None, "Source.").validate("tasklib.paths.src", "")


#################################
#     Tests for json_schema     #
#################################


def test_json_schema_groups_section() -> None:
    names = {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}
    assert json_schema()["properties"]["tasklib"]["properties"]["groups"] == {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "install": {
                **names,
                "description": "Dependency groups of env.install (comma-separated string or list).",
                "default": ["dev"],
            },
            "update": {
                **names,
                "description": "Dependency groups of env.update (comma-separated string or list).",
                "default": ["dev", "docs"],
            },
        },
    }


def test_json_schema_publishes_a_list_default_as_an_array() -> None:
    test = json_schema()["properties"]["tasklib"]["properties"]["test"]["properties"]
    assert test["cov_reports"]["default"] == ["html", "xml", "term"]


def test_json_schema_has_no_default_for_the_steps() -> None:
    check = json_schema()["properties"]["tasklib"]["properties"]["check"]["properties"]
    assert "default" not in check["tasks"]


def test_json_schema_keeps_a_scalar_default() -> None:
    check = json_schema()["properties"]["tasklib"]["properties"]["check"]["properties"]
    assert check["cov"]["default"] is False


def test_json_schema_requires_the_package_name() -> None:
    tasklib = json_schema()["properties"]["tasklib"]
    assert (tasklib["required"], tasklib["properties"]["package"]["required"]) == (
        ["package"],
        ["name"],
    )


def test_json_schema_has_no_default_for_a_derived_key() -> None:
    package = json_schema()["properties"]["tasklib"]["properties"]["package"]["properties"]
    assert "default" not in package["import_name"]


def test_json_schema_rejects_unknown_keys_of_a_section() -> None:
    sections = json_schema()["properties"]["tasklib"]["properties"]
    assert all(section["additionalProperties"] is False for section in sections.values())


def test_json_schema_allows_other_top_level_keys() -> None:
    assert "additionalProperties" not in json_schema()


def test_json_schema_lists_every_key_of_the_schema() -> None:
    sections = json_schema()["properties"]["tasklib"]["properties"]
    assert {s: list(v["properties"]) for s, v in sections.items()} == {
        s: list(options) for s, options in SCHEMA.items()
    }


def test_json_schema_steps_are_names_without_an_enum() -> None:
    sections = json_schema()["properties"]["tasklib"]["properties"]
    assert sections["check"]["properties"]["tasks"]["anyOf"] == [
        {"type": "string"},
        {"type": "array", "items": {"type": "string"}},
    ]


def test_json_schema_is_valid_json() -> None:
    assert json.loads(json.dumps(json_schema())) == json_schema()


def test_json_schema_is_deterministic() -> None:
    assert json_schema() == json_schema()


########################################
#     Tests for cov_reports schema     #
########################################


def _cov_report_pattern() -> re.Pattern[str]:
    items = json_schema()["properties"]["tasklib"]["properties"]["test"]["properties"][
        "cov_reports"
    ]["anyOf"][1]["items"]
    return re.compile(items["pattern"])


@pytest.mark.parametrize(
    "value", ["html", "term-missing", "term-missing:skip-covered", "xml:a.xml"]
)
def test_cov_reports_schema_accepts_a_valid_value(value: str) -> None:
    assert _cov_report_pattern().match(value) is not None


@pytest.mark.parametrize("value", ["", "nope", "html:", ":dir", "htmlx", "nope:dir"])
def test_cov_reports_schema_rejects_an_invalid_value(value: str) -> None:
    assert _cov_report_pattern().match(value) is None


def test_cov_reports_schema_items_are_strings() -> None:
    items = json_schema()["properties"]["tasklib"]["properties"]["test"]["properties"][
        "cov_reports"
    ]["anyOf"][1]["items"]
    assert items["type"] == "string"


#############################
#     Tests for Unset     #
#############################


def test_unset_is_not_none() -> None:
    assert Unset() is not None


def test_unset_is_a_string_so_that_invoke_keeps_the_text_of_a_variable() -> None:
    assert isinstance(Unset(), str)
