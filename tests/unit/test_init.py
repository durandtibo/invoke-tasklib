from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

import pytest
from invoke.collection import Collection
from invoke.tasks import Task

import invoke_tasklib
from invoke_tasklib import (
    _MODULES,
    _installed_version,
    _matches,
    _warn_if_unsupported_platform,
    check,
    clean,
    doc,
    env,
    fix,
    formatting,
    imports,
    lint,
    make_ns,
    release,
    security,
    show,
    testing,
    typecheck,
)
from invoke_tasklib.config import default_config

if TYPE_CHECKING:
    from types import ModuleType

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
        "fix.all",
        "format.check-docstrings",
        "format.check-python",
        "format.check-shell",
        "format.check-shell-format",
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
        "fix",
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


def test_make_ns_exclude_a_namespace_keeps_its_step_in_check() -> None:
    make_ns(exclude="lint")
    assert "lint" in check._STEPS


def test_make_ns_exclude_a_namespace_keeps_its_step_in_fix() -> None:
    make_ns(exclude="format")
    assert "format-python" in fix._STEPS


def test_make_ns_exclude_a_namespace_keeps_the_steps_of_check() -> None:
    steps = dict(check._STEPS)
    make_ns(exclude="lint")
    assert steps == check._STEPS


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


@pytest.mark.parametrize("name", sorted(ns.task_names))
def test_task_options_are_keyword_only(name: str) -> None:
    parameters = list(inspect.signature(ns[name].body).parameters.values())[1:]
    assert [p.name for p in parameters if p.kind is not inspect.Parameter.KEYWORD_ONLY] == []


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
        "fix.all",
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


#####################################################
#     Tests for the removed `invoke_tasklib.ns`     #
#####################################################


def test_module_level_ns_is_removed() -> None:
    assert not hasattr(invoke_tasklib, "ns")


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


#########################################
#     Tests for the Windows warning     #
#########################################


def test_warn_if_unsupported_platform_warns_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    with pytest.warns(RuntimeWarning, match=r"does not support Windows"):
        _warn_if_unsupported_platform()


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_warn_if_unsupported_platform_is_silent_on_posix(
    monkeypatch: pytest.MonkeyPatch, recwarn: pytest.WarningsRecorder, platform: str
) -> None:
    monkeypatch.setattr("sys.platform", platform)
    _warn_if_unsupported_platform()
    assert len(recwarn) == 0


def test_make_ns_warns_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    with pytest.warns(RuntimeWarning, match=r"does not support Windows"):
        make_ns()


def test_make_ns_blames_the_caller_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    with pytest.warns(RuntimeWarning, match=r"does not support Windows") as record:
        make_ns()
    assert record[0].filename == __file__


#########################################
#     Tests for the NAMESPACE names     #
#########################################

_TASK_MODULES = [
    check,
    clean,
    doc,
    env,
    fix,
    formatting,
    imports,
    lint,
    release,
    security,
    show,
    testing,
    typecheck,
]


@pytest.mark.parametrize(
    ("module", "namespace"),
    [
        (check, "check"),
        (clean, "clean"),
        (doc, "doc"),
        (env, "env"),
        (fix, "fix"),
        (formatting, "format"),
        (imports, "imports"),
        (lint, "lint"),
        (release, "release"),
        (security, "security"),
        (show, "config"),
        (testing, "test"),
        (typecheck, "types"),
    ],
)
def test_namespace_of_a_task_module(module: ModuleType, namespace: str) -> None:
    assert namespace == module.NAMESPACE


def test_modules_are_keyed_by_their_namespace() -> None:
    assert all(namespace == module.NAMESPACE for namespace, module in _MODULES.items())


def test_every_task_module_is_registered() -> None:
    assert set(_MODULES.values()) == set(_TASK_MODULES)


def test_namespaces_are_unique() -> None:
    assert len({module.NAMESPACE for module in _TASK_MODULES}) == len(_TASK_MODULES)


def test_from_module_with_the_namespace_keeps_the_task_names() -> None:
    ns = Collection.from_module(testing, name=testing.NAMESPACE)
    assert "test.unit" in [f"{ns.name}.{task}" for task in ns.tasks]
