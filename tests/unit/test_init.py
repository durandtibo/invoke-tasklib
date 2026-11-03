from __future__ import annotations

import pytest
from invoke.collection import Collection

from invoke_tasklib import ns


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
    }


def test_ns_contains_clean_task() -> None:
    assert "clean" in ns.tasks


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
