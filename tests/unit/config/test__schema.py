from __future__ import annotations

import json
from dataclasses import fields

import pytest

from invoke_tasklib import config as config_module
from invoke_tasklib.config import (
    DEFAULT_CHECK,
    DEFAULT_FIX,
    DEFAULT_GROUPS,
    DEFAULT_PACKAGE,
    DEFAULT_PATHS,
    DEFAULT_TEST,
    SCHEMA,
    CheckConfig,
    GroupsConfig,
    PackageConfig,
    PathsConfig,
    default_config,
    json_schema,
    main,
)
from invoke_tasklib.config._schema import _defaults, _path, _timeout

####################################
#     Tests for default_config     #
####################################


def test_default_config_has_the_six_sections() -> None:
    assert sorted(default_config()) == ["check", "fix", "groups", "package", "paths", "test"]


def test_default_config_is_the_defaults() -> None:
    assert default_config() == {
        "package": DEFAULT_PACKAGE,
        "paths": DEFAULT_PATHS,
        "groups": DEFAULT_GROUPS,
        "test": DEFAULT_TEST,
        "check": DEFAULT_CHECK,
        "fix": DEFAULT_FIX,
    }


def test_default_config_returns_new_dicts() -> None:
    default_config()["paths"]["src"] = "changed"
    assert DEFAULT_PATHS["src"] is None


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
    assert list(SCHEMA) == ["package", "paths", "groups", "test", "check", "fix"]


@pytest.mark.parametrize("section", sorted(_SECTION_CLASSES))
def test_schema_keys_are_the_fields_of_the_section_dataclass(section: str) -> None:
    assert list(SCHEMA[section]) == [f.name for f in fields(_SECTION_CLASSES[section])]


_OPTIONS = [(s, k) for s, options in SCHEMA.items() for k in options]


_OPTIONS_WITH_DEFAULT = [(s, k) for s, k in _OPTIONS if SCHEMA[s][k].default is not None]


@pytest.mark.parametrize(("section", "key"), _OPTIONS_WITH_DEFAULT)
def test_schema_default_is_valid(section: str, key: str) -> None:
    option = SCHEMA[section][key]
    assert option.validate(option.default) is not None


@pytest.mark.parametrize(("section", "key"), _OPTIONS)
def test_schema_option_has_a_description(section: str, key: str) -> None:
    assert SCHEMA[section][key].doc.endswith((".", ")"))


@pytest.mark.parametrize(("section", "key"), _OPTIONS)
def test_schema_option_has_a_json_type(section: str, key: str) -> None:
    schema = SCHEMA[section][key].json_schema
    assert "type" in schema or "anyOf" in schema


@pytest.mark.parametrize(("section", "key"), _OPTIONS)
def test_schema_option_validation_error_names_the_key(section: str, key: str) -> None:
    with pytest.raises(ValueError, match=rf"tasklib\.{section}\.{key}"):
        SCHEMA[section][key].validate(object())


def test_schema_default_dicts_are_derived_from_the_schema() -> None:
    assert {k: o.default for k, o in SCHEMA["test"].items()} == DEFAULT_TEST


def test_defaults_of_a_section() -> None:
    assert _defaults("check") == {
        "tasks": "format-python,format-docstrings,lint,types,imports,unit"
    }


def test_defaults_returns_a_new_dict() -> None:
    _defaults("groups")["install"] = "changed"
    assert _defaults("groups")["install"] == "dev"


def test_timeout_option() -> None:
    option = _timeout("unit_timeout", 10, "Timeout.")
    assert (option.default, option.json_schema) == (10, {"type": "integer", "minimum": 1})


def test_timeout_option_rejects_zero() -> None:
    with pytest.raises(ValueError, match=r"'tasklib.test.unit_timeout' must be an integer >= 1"):
        _timeout("unit_timeout", 10, "Timeout.").validate(0)


def test_path_option() -> None:
    option = _path("src", None, "Source.")
    assert (option.default, option.doc) == (None, "Source.")


def test_path_option_rejects_an_empty_string() -> None:
    with pytest.raises(ValueError, match=r"'tasklib.paths.src' must be a non-empty string"):
        _path("src", None, "Source.").validate("")


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
                "default": "dev",
            },
            "update": {
                **names,
                "description": "Dependency groups of env.update (comma-separated string or list).",
                "default": "dev,docs",
            },
        },
    }


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


def test_json_schema_check_steps_are_listed() -> None:
    sections = json_schema()["properties"]["tasklib"]["properties"]
    assert "docs" in sections["check"]["properties"]["tasks"]["anyOf"][1]["items"]["enum"]


def test_json_schema_is_valid_json() -> None:
    assert json.loads(json.dumps(json_schema())) == json_schema()


def test_json_schema_is_deterministic() -> None:
    assert json_schema() == json_schema()


###########################
#     Tests for main      #
###########################


def test_main_returns_0() -> None:
    assert main([]) == 0


def test_main_prints_the_schema(capsys: pytest.CaptureFixture[str]) -> None:
    main([])
    assert json.loads(capsys.readouterr().out) == json_schema()


def test_main_rejects_arguments() -> None:
    assert main(["--bad"]) == 2


def test_main_prints_the_usage_when_it_rejects_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["--bad"])
    assert capsys.readouterr().out == "usage: python -m invoke_tasklib.config\n"
