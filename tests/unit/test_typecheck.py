from __future__ import annotations

from invoke_tasklib import typecheck
from tests.helpers import commands, make_context


def test_check() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    typecheck.check(c)
    assert commands(c) == ["ty check"]


def test_check_complete() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    typecheck.check(c, complete=True)
    assert commands(c) == ["ty check", "pyright"]


def test_check_args() -> None:
    c = make_context()
    typecheck.check(c, args="--python-version 3.12")
    assert commands(c) == ["ty check --python-version 3.12"]


def test_check_paths() -> None:
    c = make_context()
    typecheck.check(c, paths="src/a.py")
    assert commands(c) == ["ty check src/a.py"]


def test_check_complete_passes_paths_but_not_args_to_pyright() -> None:
    c = make_context()
    typecheck.check(c, complete=True, args="--python-version 3.12", paths="src/a.py")
    assert commands(c) == ["ty check --python-version 3.12 src/a.py", "pyright src/a.py"]
