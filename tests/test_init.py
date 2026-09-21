from __future__ import annotations

from invoke.collection import Collection

from invoke_tasklib import ns


def test_ns_is_collection() -> None:
    assert isinstance(ns, Collection)


def test_ns_contains_expected_subcollections() -> None:
    assert set(ns.collections.keys()) == {"format", "lint", "types", "test", "env", "release"}
