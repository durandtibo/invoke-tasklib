from __future__ import annotations

import pytest
from invoke.exceptions import Exit

from invoke_tasklib import typecheck
from tests.helpers import commands, make_context

_CFG = {"package": {"name": "mypkg"}}


def test_check() -> None:
    c = make_context(_CFG)
    typecheck.check(c)
    assert commands(c) == ["ty check"]


def test_check_complete() -> None:
    c = make_context(_CFG)
    typecheck.check(c, complete=True)
    assert commands(c) == ["ty check", "pyright"]


def test_check_args() -> None:
    c = make_context(_CFG)
    typecheck.check(c, args="--python-version 3.12")
    assert commands(c) == ["ty check --python-version 3.12"]


def test_check_paths() -> None:
    c = make_context(_CFG)
    typecheck.check(c, paths="src/a.py")
    assert commands(c) == ["ty check src/a.py"]


def test_check_complete_passes_paths_but_not_args_to_pyright() -> None:
    c = make_context(_CFG)
    typecheck.check(c, complete=True, args="--python-version 3.12", paths="src/a.py")
    assert commands(c) == ["ty check --python-version 3.12 src/a.py", "pyright src/a.py"]


def test_check_complete_passes_pyright_args_to_pyright() -> None:
    c = make_context(_CFG)
    typecheck.check(c, complete=True, pyright_args="--pythonversion 3.12")
    assert commands(c) == ["ty check", "pyright --pythonversion 3.12"]


def test_check_pyright_args_are_not_passed_to_ty() -> None:
    c = make_context(_CFG)
    typecheck.check(c, complete=True, pyright_args="--pythonversion 3.12")
    assert commands(c)[0] == "ty check"


def test_check_pyright_args_are_ignored_without_complete() -> None:
    c = make_context(_CFG)
    typecheck.check(c, pyright_args="--pythonversion 3.12")
    assert commands(c) == ["ty check"]


def test_check_complete_passes_args_and_paths_to_each_tool() -> None:
    c = make_context(_CFG)
    typecheck.check(
        c, complete=True, args="-v", paths="src/a.py", pyright_args="--pythonversion 3.12"
    )
    assert commands(c) == ["ty check -v src/a.py", "pyright --pythonversion 3.12 src/a.py"]


def test_check_pyright_args_are_quoted() -> None:
    c = make_context(_CFG)
    typecheck.check(c, complete=True, pyright_args="--project 'my dir'")
    assert commands(c)[1] == "pyright --project 'my dir'"


def test_check_rejects_unbalanced_pyright_args() -> None:
    with pytest.raises(Exit, match=r"Cannot parse the value of --pyright-args"):
        typecheck.check(make_context(_CFG), complete=True, pyright_args="'unclosed")


def _with_checker(checker: str) -> dict:
    return {**_CFG, "types": {"checker": checker}}


@pytest.mark.parametrize(
    ("checker", "command"), [("ty", "ty check"), ("pyright", "pyright"), ("mypy", "mypy")]
)
def test_check_runs_the_configured_checker(checker: str, command: str) -> None:
    c = make_context(_with_checker(checker))
    typecheck.check(c)
    assert commands(c) == [command]


def test_check_complete_with_mypy_adds_pyright() -> None:
    c = make_context(_with_checker("mypy"))
    typecheck.check(c, complete=True)
    assert commands(c) == ["mypy", "pyright"]


def test_check_complete_with_pyright_does_not_run_it_twice() -> None:
    c = make_context(_with_checker("pyright"))
    typecheck.check(c, complete=True)
    assert commands(c) == ["pyright"]


def test_check_args_go_to_the_configured_checker() -> None:
    c = make_context(_with_checker("mypy"))
    typecheck.check(c, args="--strict", paths="src")
    assert commands(c) == ["mypy --strict src"]


def test_check_says_which_checker_it_runs(capsys: pytest.CaptureFixture[str]) -> None:
    typecheck.check(make_context(_with_checker("mypy")))
    assert capsys.readouterr().out == "🔬 Checking type hints with mypy...\n✅ Type check passed\n"
