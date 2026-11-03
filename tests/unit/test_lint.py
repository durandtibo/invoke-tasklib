from __future__ import annotations

import pytest

from invoke_tasklib import lint
from tests.helpers import commands, make_context


@pytest.fixture(autouse=True)
def _outside_github_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


def test_check_python() -> None:
    c = make_context()
    lint.check_python(c)
    assert commands(c) == ["ruff check ."]


def test_check_python_uses_github_format_in_github_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    c = make_context()
    lint.check_python(c)
    assert commands(c) == ["ruff check --output-format=github ."]


def test_check_python_explicit_format_wins_in_github_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    c = make_context()
    lint.check_python(c, output_format="concise")
    assert commands(c) == ["ruff check --output-format=concise ."]


def test_check_python_explicit_format() -> None:
    c = make_context()
    lint.check_python(c, output_format="full")
    assert commands(c) == ["ruff check --output-format=full ."]


def test_check_python_ignores_other_github_actions_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    c = make_context()
    lint.check_python(c)
    assert commands(c) == ["ruff check ."]


def test_fix_python() -> None:
    c = make_context()
    lint.fix_python(c)
    assert commands(c) == ["ruff check --fix ."]


def test_check_python_args() -> None:
    c = make_context()
    lint.check_python(c, args="--select E")
    assert commands(c) == ["ruff check --select E ."]


def test_check_python_paths() -> None:
    c = make_context()
    lint.check_python(c, paths="a.py b.py")
    assert commands(c) == ["ruff check a.py b.py"]


def test_check_python_args_and_format_and_paths() -> None:
    c = make_context()
    lint.check_python(c, output_format="full", args="--select E", paths="a.py")
    assert commands(c) == ["ruff check --output-format=full --select E a.py"]


def test_fix_python_args() -> None:
    c = make_context()
    lint.fix_python(c, args="--select I")
    assert commands(c) == ["ruff check --fix --select I ."]


def test_fix_python_paths() -> None:
    c = make_context()
    lint.fix_python(c, paths="a.py")
    assert commands(c) == ["ruff check --fix a.py"]


###################################
#     Tests for check_spelling     #
###################################


def test_check_spelling() -> None:
    c = make_context()
    lint.check_spelling(c)
    assert commands(c) == ["codespell ."]


def test_check_spelling_args() -> None:
    c = make_context()
    lint.check_spelling(c, args="--ignore-words-list foo")
    assert commands(c) == ["codespell --ignore-words-list foo ."]


def test_check_spelling_paths() -> None:
    c = make_context()
    lint.check_spelling(c, paths="docs README.md")
    assert commands(c) == ["codespell docs README.md"]


################################
#     Tests for pre_commit     #
################################


def test_pre_commit() -> None:
    c = make_context()
    lint.pre_commit(c)
    assert commands(c) == ["pre-commit run --all-files"]


def test_pre_commit_args() -> None:
    c = make_context()
    lint.pre_commit(c, args="ruff-format")
    assert commands(c) == ["pre-commit run --all-files ruff-format"]
