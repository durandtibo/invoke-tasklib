from __future__ import annotations

import pytest
from invoke.collection import Collection
from invoke.tasks import Task

import invoke_tasklib
from invoke_tasklib import _installed_version, _matches, _shared_ns, make_ns
from invoke_tasklib.config import default_config

ns = make_ns()


def test_ns_is_collection() -> None:
    assert isinstance(ns, Collection)


def test_ns_contains_the_complete_list_of_tasks() -> None:
    assert sorted(ns.task_names) == [
        "check.all",
        "clean.all",
        "clean.pycache",
        "config.show",
        "doc.build",
        "doc.publish-dev",
        "doc.publish-latest",
        "doc.serve",
        "env.check-tools",
        "env.create-venv",
        "env.install",
        "env.show-installed-packages",
        "env.show-python-config",
        "env.update",
        "format.check-docstrings",
        "format.check-python",
        "format.check-shell",
        "format.fix-docstrings",
        "format.fix-python",
        "format.fix-shell",
        "imports.check-cycles",
        "imports.check-isolated",
        "lint.check-python",
        "lint.check-spelling",
        "lint.fix-python",
        "lint.pre-commit",
        "release.build",
        "release.publish",
        "security.audit",
        "test.all",
        "test.benchmark",
        "test.coverage-report",
        "test.doctest",
        "test.doctest-markdown",
        "test.doctest-src",
        "test.functional",
        "test.integration",
        "test.unit",
        "types.check",
    ]


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
        "config",
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
    assert "release.publish" not in make_ns(exclude=["release.publish"]).task_names


def test_make_ns_exclude_a_task_keeps_its_siblings() -> None:
    assert "release.build" in make_ns(exclude=["release.publish"]).task_names


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
        ("release.publish", ["release"], True),
        ("release.publish", ["release.publish"], True),
        ("release.publish", ["release.build"], False),
        ("release.publish", ["rel"], False),
        ("release.publish", [], False),
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
def test_task_summary_has_no_backticks(name: str) -> None:
    summary = (ns[name].__doc__ or "").strip().splitlines()[0]
    assert "`" not in summary


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


###################################
#     Tests for the args option     #
###################################

_WITHOUT_ARGS = frozenset(
    {
        # Composite tasks: the options would be ambiguous.
        "check.all",
        "test.doctest",
        # No external tool to give arguments to.
        "clean.all",
        "clean.pycache",
        "config.show",
        "imports.check-cycles",
        "imports.check-isolated",
        # Tasks with their own, specific options.
        "doc.publish-dev",
        "doc.publish-latest",
        "env.check-tools",
        "env.create-venv",
        "env.install",
        "env.show-installed-packages",
        "env.show-python-config",
        "env.update",
    }
)


def _option_names(name: str) -> list[str]:
    return [arg.name for arg in ns[name].get_arguments()]


@pytest.mark.parametrize("name", sorted(set(ns.task_names) - _WITHOUT_ARGS))
def test_task_has_the_args_option(name: str) -> None:
    assert "args" in _option_names(name)


@pytest.mark.parametrize("name", sorted(_WITHOUT_ARGS))
def test_exception_of_the_args_option_has_no_args_option(name: str) -> None:
    assert "args" not in _option_names(name)


##########################################
#     Tests for the deprecated `ns`      #
##########################################


def test_ns_attribute_is_deprecated() -> None:
    with pytest.warns(DeprecationWarning, match=r"'invoke_tasklib\.ns' is deprecated"):
        _ = invoke_tasklib.ns


def test_ns_attribute_names_the_replacement() -> None:
    with pytest.warns(DeprecationWarning, match=r"Use 'ns = make_ns\(\)'"):
        _ = invoke_tasklib.ns


def test_ns_attribute_is_a_collection_with_all_the_tasks() -> None:
    with pytest.warns(DeprecationWarning, match=r"deprecated"):
        deprecated = invoke_tasklib.ns
    assert set(deprecated.task_names) == set(make_ns().task_names)


def test_ns_attribute_is_the_same_collection_every_time() -> None:
    with pytest.warns(DeprecationWarning, match=r"deprecated"):
        first = invoke_tasklib.ns
    with pytest.warns(DeprecationWarning, match=r"deprecated"):
        second = invoke_tasklib.ns
    assert first is second


def test_ns_attribute_is_the_shared_collection() -> None:
    with pytest.warns(DeprecationWarning, match=r"deprecated"):
        deprecated = invoke_tasklib.ns
    assert deprecated is _shared_ns()


def test_unknown_attribute_raises() -> None:
    with pytest.raises(AttributeError, match=r"module 'invoke_tasklib' has no attribute 'nope'"):
        _ = invoke_tasklib.nope


def test_make_ns_returns_a_new_collection_every_time() -> None:
    assert make_ns() is not make_ns()


##################################
#     Tests for __version__      #
##################################


def test_version_is_the_installed_version() -> None:
    assert invoke_tasklib.__version__ == _installed_version("invoke-tasklib")


def test_version_is_a_string() -> None:
    assert isinstance(invoke_tasklib.__version__, str)


def test_installed_version_of_a_distribution() -> None:
    assert _installed_version("pytest").split(".")[0].isdigit()


def test_installed_version_of_a_missing_distribution() -> None:
    assert _installed_version("no-such-distribution-xyz") == "0+unknown"
