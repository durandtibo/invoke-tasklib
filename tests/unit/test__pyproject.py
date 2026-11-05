from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import pytest
from invoke.exceptions import Exit

from invoke_tasklib import _pyproject

if TYPE_CHECKING:
    from pathlib import Path

####################################
#     Tests for read_pyproject     #
####################################


def test_read_pyproject_reads_the_file(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "foo"\n')
    assert _pyproject.read_pyproject(path) == {"project": {"name": "foo"}}


def test_read_pyproject_missing_file_is_empty(tmp_path: Path) -> None:
    assert _pyproject.read_pyproject(tmp_path / "pyproject.toml") == {}


def test_read_pyproject_empty_file_is_empty(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text("")
    assert _pyproject.read_pyproject(path) == {}


def test_read_pyproject_reads_the_file_of_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text("[a]\nb = 1\n")
    monkeypatch.chdir(tmp_path)
    assert _pyproject.read_pyproject() == {"a": {"b": 1}}


def test_read_pyproject_invalid_file_exits_with_code_1(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text("[project\n")
    with pytest.raises(Exit, match=r"invalid TOML") as info:
        _pyproject.read_pyproject(path)
    assert info.value.code == 1


def test_read_pyproject_invalid_file_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text("[project\n")
    with pytest.raises(Exit, match=r"pyproject\.toml'"):
        _pyproject.read_pyproject(path)


def test_read_pyproject_invalid_file_gives_the_line_and_the_column(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "a"\nversion = \n')
    with pytest.raises(Exit, match=r"\(line 3, column 11\): Invalid value\. Fix the file"):
        _pyproject.read_pyproject(path)


#####################################
#     Tests for _describe_error     #
#####################################


def test_describe_error_gives_the_position_and_the_reason() -> None:
    with pytest.raises(tomllib.TOMLDecodeError) as info:
        tomllib.loads("a = \n")
    assert _pyproject._describe_error(info.value) == "(line 1, column 5): Invalid value"


def test_describe_error_without_a_position_gives_the_message() -> None:
    with pytest.raises(tomllib.TOMLDecodeError) as info:
        tomllib.loads("a = 'x")
    assert _pyproject._describe_error(info.value) == str(info.value)
