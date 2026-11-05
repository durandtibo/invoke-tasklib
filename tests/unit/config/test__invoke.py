from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from invoke.config import Config

from invoke_tasklib.config._invoke import (
    ENV_LABEL,
    LEVELS,
    PROJECT_PREFIX_ATTRIBUTE,
    is_unset,
    levels,
    missing_internals,
    project_root,
)
from invoke_tasklib.config._schema import Unset

_LEVEL_ATTRIBUTES = [attribute for attribute, _ in LEVELS]


# The module reads these private attributes of Invoke with `getattr` or
# `hasattr`, which would hide a rename in a new version of Invoke:
# these tests make it fail loudly.
@pytest.mark.parametrize("attribute", _LEVEL_ATTRIBUTES)
def test_levels_exist_on_an_invoke_config(attribute: str) -> None:
    assert hasattr(Config(), attribute)


@pytest.mark.parametrize("attribute", _LEVEL_ATTRIBUTES)
def test_levels_of_an_invoke_config_are_dicts(attribute: str) -> None:
    assert isinstance(getattr(Config(), attribute), dict)


def test_project_prefix_attribute_exists_on_an_invoke_config() -> None:
    assert hasattr(Config(), PROJECT_PREFIX_ATTRIBUTE)


def test_project_prefix_attribute_holds_the_project_location(tmp_path: Path) -> None:
    assert Path(getattr(Config(project_location=tmp_path), PROJECT_PREFIX_ATTRIBUTE)) == tmp_path


##################################
#     Tests for project_root     #
##################################


def test_project_root_is_the_resolved_project_location(tmp_path: Path) -> None:
    assert project_root(Config(project_location=tmp_path)) == tmp_path.resolve()


def test_project_root_is_none_without_a_location() -> None:
    assert project_root(Config()) is None


def test_project_root_without_the_attribute_warns() -> None:
    with pytest.warns(RuntimeWarning, match=r"this version of Invoke has no '_project_prefix'"):
        project_root(SimpleNamespace())


def test_project_root_without_the_attribute_is_none() -> None:
    with pytest.warns(RuntimeWarning, match=r"Cannot check that inv runs"):
        assert project_root(SimpleNamespace()) is None


def test_project_root_does_not_warn_with_the_attribute(recwarn: pytest.WarningsRecorder) -> None:
    project_root(Config())
    assert len(recwarn) == 0


############################
#     Tests for levels     #
############################


def test_levels_yields_the_highest_priority_first() -> None:
    config = Config(defaults={"a": 1}, overrides={"b": 2})
    assert [label for _, label, _ in levels(config)] == ["override", "default"]


def test_levels_yields_the_attribute_and_the_mapping() -> None:
    config = Config(overrides={"b": 2})
    assert next(levels(config)) == ("_overrides", "override", {"b": 2})


def test_levels_skips_the_empty_sources() -> None:
    assert list(levels(SimpleNamespace(_defaults={}, _overrides={}))) == []


def test_levels_skips_a_missing_attribute() -> None:
    assert list(levels(SimpleNamespace(_overrides={"b": 2}))) == [
        ("_overrides", "override", {"b": 2})
    ]


def test_levels_labels_the_environment_variables() -> None:
    assert next(levels(SimpleNamespace(_env={"b": 2})))[1] == ENV_LABEL


#######################################
#     Tests for missing_internals     #
#######################################


def test_missing_internals_of_an_invoke_config_is_empty() -> None:
    assert missing_internals(Config()) == []


@pytest.mark.parametrize("attribute", [*_LEVEL_ATTRIBUTES, "_project_prefix"])
def test_missing_internals_names_a_missing_attribute(attribute: str) -> None:
    config = Config()
    object.__delattr__(config, attribute)
    assert missing_internals(config) == [attribute]


def test_missing_internals_lists_the_missing_attributes_in_order() -> None:
    config = Config()
    object.__delattr__(config, "_project_prefix")
    object.__delattr__(config, "_env")
    assert missing_internals(config) == ["_env", "_project_prefix"]


##############################
#     Tests for is_unset     #
##############################


def test_is_unset_true_for_unset() -> None:
    assert is_unset(Unset()) is True


@pytest.mark.parametrize("value", ["", "x", 0, None, False])
def test_is_unset_false_for_a_value(value: object) -> None:
    assert is_unset(value) is False
