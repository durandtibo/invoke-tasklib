from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit

from invoke_tasklib import formatting
from tests.helpers import commands, make_context

if TYPE_CHECKING:
    from pathlib import Path


def test_check_python() -> None:
    c = make_context()
    formatting.check_python(c)
    assert commands(c) == ["ruff format --check ."]


def test_check_docstrings_uses_configured_src_path() -> None:
    c = make_context({"package": {"name": "mypkg"}, "paths": {"src": "src/mypkg"}})
    formatting.check_docstrings(c)
    assert commands(c) == ["docformatter --config ./pyproject.toml --check src/mypkg"]


def test_check_docstrings_without_package_name_exits_with_a_message() -> None:
    with pytest.raises(Exit, match=r"'tasklib.package.name' must be set"):
        formatting.check_docstrings(MockContext(config=Config(), run=True))


def test_fix_python() -> None:
    c = make_context()
    formatting.fix_python(c)
    assert commands(c) == ["ruff format ."]


def test_fix_docstrings_uses_configured_src_path() -> None:
    c = make_context({"package": {"name": "mypkg"}, "paths": {"src": "src/mypkg"}})
    formatting.fix_docstrings(c)
    assert commands(c) == ["docformatter --config ./pyproject.toml --in-place src/mypkg"]


@pytest.fixture
def scripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "run.sh").write_text("")
    (tmp_path / "top.sh").write_text("")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "activate.sh").write_text("")
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def no_scripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


@pytest.mark.usefixtures("scripts")
def test_check_shell() -> None:
    c = make_context()
    formatting.check_shell(c)
    assert commands(c) == ["shellcheck -- src/run.sh top.sh"]


@pytest.mark.usefixtures("scripts")
def test_check_shell_with_args() -> None:
    c = make_context()
    formatting.check_shell(c, args="-x")
    assert commands(c) == ["shellcheck -x -- src/run.sh top.sh"]


@pytest.mark.usefixtures("no_scripts")
def test_check_shell_without_script_runs_nothing() -> None:
    c = make_context()
    formatting.check_shell(c)
    assert commands(c) == []


@pytest.mark.usefixtures("no_scripts")
def test_check_shell_without_script_says_it_skips(capsys: pytest.CaptureFixture[str]) -> None:
    formatting.check_shell(make_context())
    assert "⏭️  No shell script found: skipping" in capsys.readouterr().out


def test_check_shell_with_paths_does_not_search_the_project() -> None:
    c = make_context()
    formatting.check_shell(c, paths="a.sh 'b c.sh'")
    assert commands(c) == ["shellcheck -- a.sh 'b c.sh'"]


def test_check_shell_with_args_and_paths() -> None:
    c = make_context()
    formatting.check_shell(c, args="-x", paths="a.sh")
    assert commands(c) == ["shellcheck -x -- a.sh"]


def test_fix_shell_with_args_and_paths() -> None:
    c = make_context()
    formatting.fix_shell(c, args="-i 2", paths="a.sh")
    assert commands(c) == ["shfmt -l -w -i 2 -- a.sh"]


@pytest.mark.usefixtures("scripts")
def test_fix_shell_with_args() -> None:
    c = make_context()
    formatting.fix_shell(c, args="-i 2")
    assert commands(c) == ["shfmt -l -w -i 2 -- src/run.sh top.sh"]


@pytest.mark.usefixtures("scripts")
def test_fix_shell() -> None:
    c = make_context()
    formatting.fix_shell(c)
    assert commands(c) == ["shfmt -l -w -- src/run.sh top.sh"]


@pytest.mark.usefixtures("no_scripts")
def test_fix_shell_without_script_runs_nothing() -> None:
    c = make_context()
    formatting.fix_shell(c)
    assert commands(c) == []


def test_check_python_args() -> None:
    c = make_context()
    formatting.check_python(c, args="--diff")
    assert commands(c) == ["ruff format --check --diff ."]


def test_check_python_paths() -> None:
    c = make_context()
    formatting.check_python(c, paths="a.py")
    assert commands(c) == ["ruff format --check a.py"]


def test_fix_python_args() -> None:
    c = make_context()
    formatting.fix_python(c, args="--diff")
    assert commands(c) == ["ruff format --diff ."]


def test_fix_python_paths() -> None:
    c = make_context()
    formatting.fix_python(c, paths="a.py")
    assert commands(c) == ["ruff format a.py"]


def test_check_docstrings_paths_replace_src() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    formatting.check_docstrings(c, paths="src/mypkg/a.py")
    assert commands(c) == ["docformatter --config ./pyproject.toml --check src/mypkg/a.py"]


def test_check_docstrings_args() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    formatting.check_docstrings(c, args="--wrap-summaries 80")
    assert commands(c) == [
        "docformatter --config ./pyproject.toml --check --wrap-summaries 80 src/mypkg"
    ]


def test_fix_docstrings_paths_replace_src() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    formatting.fix_docstrings(c, paths="src/mypkg/a.py")
    assert commands(c) == ["docformatter --config ./pyproject.toml --in-place src/mypkg/a.py"]


def test_fix_docstrings_args() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    formatting.fix_docstrings(c, args="--wrap-summaries 80")
    assert commands(c) == [
        "docformatter --config ./pyproject.toml --in-place --wrap-summaries 80 src/mypkg"
    ]


#####################################
#     Tests for _shell_command      #
#####################################


@pytest.mark.usefixtures("scripts")
def test_shell_command_searches_the_project_by_default() -> None:
    assert (
        formatting._shell_command(make_context(), "shfmt -l", None, None)
        == "shfmt -l -- src/run.sh top.sh"
    )


@pytest.mark.usefixtures("no_scripts")
def test_shell_command_without_script_is_none() -> None:
    assert formatting._shell_command(make_context(), "shfmt -l", None, None) is None


@pytest.mark.usefixtures("no_scripts")
def test_shell_command_with_paths_does_not_need_a_script() -> None:
    assert formatting._shell_command(make_context(), "shfmt -l", None, "a.sh") == "shfmt -l -- a.sh"


def test_shell_command_puts_args_before_the_separator() -> None:
    assert formatting._shell_command(make_context(), "shellcheck", "-x -e SC1091", "a.sh") == (
        "shellcheck -x -e SC1091 -- a.sh"
    )


def test_shell_command_quotes_the_paths() -> None:
    assert formatting._shell_command(make_context(), "shellcheck", None, "'a b.sh' ';rm'") == (
        "shellcheck -- 'a b.sh' ';rm'"
    )


def test_shell_command_rejects_an_unclosed_quote() -> None:
    with pytest.raises(Exit, match="--paths"):
        formatting._shell_command(make_context(), "shellcheck", None, "'a.sh")
