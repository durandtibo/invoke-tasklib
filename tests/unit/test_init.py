from __future__ import annotations

import pytest
from invoke.collection import Collection
from invoke.tasks import Task

from invoke_tasklib import _matches, make_ns, ns
from invoke_tasklib.config import default_config


def test_ns_is_collection() -> None:
    assert isinstance(ns, Collection)


def test_ns_contains_expected_subcollections() -> None:
    assert set(ns.collections.keys()) == {
        "format",
        "lint",
        "imports",
        "types",
        "test",
        "env",
        "release",
        "doc",
        "security",
        "clean",
        "check",
    }


def test_ns_contains_clean_namespace() -> None:
    assert set(ns.collections["clean"].tasks) == {"all", "pycache"}


def test_ns_clean_is_the_default_task_of_the_clean_namespace() -> None:
    assert ns.collections["clean"].default == "all"


def test_ns_contains_clean_task_alias() -> None:
    assert ns.task_names["clean.all"] == ["clean"]


#############################
#     Tests for make_ns     #
#############################


def test_make_ns_returns_a_new_collection_each_time() -> None:
    assert make_ns() is not make_ns()


def test_make_ns_default_has_the_same_tasks_as_ns() -> None:
    assert set(make_ns().task_names) == set(ns.task_names)


def test_make_ns_adding_a_task_does_not_change_other_collections() -> None:
    other = make_ns()
    other.add_task(Task(lambda _c: None, name="extra"))
    assert "extra" not in make_ns().tasks


def test_make_ns_exclude_a_namespace() -> None:
    assert "doc" not in make_ns(exclude=["doc"]).collections


def test_make_ns_exclude_a_bare_string_is_one_name() -> None:
    assert "doc" not in make_ns(exclude="doc").collections


def test_make_ns_exclude_a_bare_string_keeps_the_other_namespaces() -> None:
    assert "lint" in make_ns(exclude="doc").collections


def test_make_ns_include_a_bare_string_is_one_name() -> None:
    assert set(make_ns(include="lint").collections) == {"lint"}


def test_make_ns_unknown_bare_string_names_the_whole_string() -> None:
    with pytest.raises(
        ValueError, match=r"Unknown task or namespace \['relese'\]"
    ):  # codespell:ignore relese
        make_ns(exclude="relese")  # codespell:ignore relese


def test_make_ns_exclude_a_task() -> None:
    assert "release.pypi" not in make_ns(exclude=["release.pypi"]).task_names


def test_make_ns_exclude_a_task_keeps_its_siblings() -> None:
    assert "release.build" in make_ns(exclude=["release.pypi"]).task_names


def test_make_ns_exclude_all_tasks_of_a_namespace_removes_it() -> None:
    assert "types" not in make_ns(exclude=["types.check"]).collections


def test_make_ns_include_a_namespace() -> None:
    assert set(make_ns(include=["lint"]).task_names) == {
        "lint.check-python",
        "lint.check-spelling",
        "lint.fix-python",
        "lint.pre-commit",
    }


def test_make_ns_include_a_task() -> None:
    assert set(make_ns(include=["test.unit"]).task_names) == {"test.unit"}


def test_make_ns_include_then_exclude() -> None:
    ns_ = make_ns(include=["lint"], exclude=["lint.fix-python", "lint.pre-commit"])
    assert set(ns_.task_names) == {"lint.check-python", "lint.check-spelling"}


def test_make_ns_include_empty_is_an_empty_collection() -> None:
    assert make_ns(include=[]).task_names == {}


def test_make_ns_keeps_the_default_task_of_clean() -> None:
    assert make_ns(include=["clean"]).collections["clean"].default == "all"


def test_make_ns_unknown_name_in_exclude() -> None:
    with pytest.raises(ValueError, match=r"Unknown task or namespace \['relese'\]"):
        make_ns(exclude=["relese"])  # codespell:ignore relese


def test_make_ns_unknown_name_in_include() -> None:
    with pytest.raises(ValueError, match=r"Unknown task or namespace \['lnt'\]"):
        make_ns(include=["lnt"])


############################
#     Tests for _matches   #
############################


@pytest.mark.parametrize(
    ("name", "patterns", "expected"),
    [
        ("release.pypi", ["release"], True),
        ("release.pypi", ["release.pypi"], True),
        ("release.pypi", ["release.build"], False),
        ("release.pypi", ["rel"], False),
        ("release.pypi", [], False),
    ],
)
def test_matches(name: str, patterns: list[str], expected: bool) -> None:
    assert _matches(name, patterns) is expected


####################################
#     Tests for task help text     #
####################################


@pytest.mark.parametrize("name", sorted(ns.task_names))
def test_task_summary_is_a_single_line(name: str) -> None:
    lines = (ns[name].__doc__ or "").strip().splitlines()
    assert len(lines) == 1 or lines[1].strip() == ""


@pytest.mark.parametrize("name", sorted(ns.task_names))
def test_task_summary_fits_in_the_task_list(name: str) -> None:
    summary = (ns[name].__doc__ or "").strip().splitlines()[0]
    assert len(summary) <= 60


@pytest.mark.parametrize("name", sorted(ns.task_names))
def test_task_summary_is_a_sentence(name: str) -> None:
    summary = (ns[name].__doc__ or "").strip().splitlines()[0]
    assert summary.endswith(".")


@pytest.mark.parametrize("name", sorted(ns.task_names))
def test_task_options_are_documented(name: str) -> None:
    assert all(arg.help for arg in ns[name].get_arguments())


def test_make_ns_registers_the_tasklib_defaults() -> None:
    assert make_ns().configuration()["tasklib"] == default_config()


def test_make_ns_registers_the_defaults_when_tasks_are_excluded() -> None:
    assert make_ns(include=[]).configuration()["tasklib"] == default_config()
