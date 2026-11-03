from __future__ import annotations

from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit

from invoke_tasklib import formatting


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


def test_check_python() -> None:
    c = _context()
    formatting.check_python(c)
    assert _commands(c) == ["ruff format --check ."]


def test_check_docstrings_uses_configured_src_path() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"src": "src/mypkg"}})
    formatting.check_docstrings(c)
    assert _commands(c) == ["docformatter --config ./pyproject.toml --check src/mypkg"]


def test_check_docstrings_without_package_name_exits_with_a_message() -> None:
    with pytest.raises(Exit, match=r"'tasklib.package.name' must be set"):
        formatting.check_docstrings(MockContext(config=Config(), run=True))


def test_fix_python() -> None:
    c = _context()
    formatting.fix_python(c)
    assert _commands(c) == ["ruff format ."]


def test_fix_docstrings_uses_configured_src_path() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"src": "src/mypkg"}})
    formatting.fix_docstrings(c)
    assert _commands(c) == ["docformatter --config ./pyproject.toml --in-place src/mypkg"]


def test_check_shell() -> None:
    c = _context()
    formatting.check_shell(c)
    assert _commands(c) == [f"{formatting._FIND_SH} | xargs -0 -r shellcheck --"]


def test_fix_shell() -> None:
    c = _context()
    formatting.fix_shell(c)
    assert _commands(c) == [f"{formatting._FIND_SH} | xargs -0 -r shfmt -l -w --"]


##############################
#     Tests for _FIND_SH     #
##############################


def test_find_sh_command() -> None:
    assert formatting._FIND_SH == (
        "find . \\( -name .git -o -name .pytest_cache -o -name .venv -o -name build "
        "-o -name dist -o -name node_modules -o -name site \\) -type d -prune "
        "-o -name '*.sh' -type f -print0"
    )


def test_check_python_args() -> None:
    c = _context()
    formatting.check_python(c, args="--diff")
    assert _commands(c) == ["ruff format --check --diff ."]


def test_check_python_paths() -> None:
    c = _context()
    formatting.check_python(c, paths="a.py")
    assert _commands(c) == ["ruff format --check a.py"]


def test_fix_python_args() -> None:
    c = _context()
    formatting.fix_python(c, args="--diff")
    assert _commands(c) == ["ruff format --diff ."]


def test_fix_python_paths() -> None:
    c = _context()
    formatting.fix_python(c, paths="a.py")
    assert _commands(c) == ["ruff format a.py"]


def test_check_docstrings_paths_replace_src() -> None:
    c = _context({"package": {"name": "mypkg"}})
    formatting.check_docstrings(c, paths="src/mypkg/a.py")
    assert _commands(c) == ["docformatter --config ./pyproject.toml --check src/mypkg/a.py"]


def test_check_docstrings_args() -> None:
    c = _context({"package": {"name": "mypkg"}})
    formatting.check_docstrings(c, args="--wrap-summaries 80")
    assert _commands(c) == [
        "docformatter --config ./pyproject.toml --check --wrap-summaries 80 src/mypkg"
    ]


def test_fix_docstrings_paths_replace_src() -> None:
    c = _context({"package": {"name": "mypkg"}})
    formatting.fix_docstrings(c, paths="src/mypkg/a.py")
    assert _commands(c) == ["docformatter --config ./pyproject.toml --in-place src/mypkg/a.py"]


def test_fix_docstrings_args() -> None:
    c = _context({"package": {"name": "mypkg"}})
    formatting.fix_docstrings(c, args="--wrap-summaries 80")
    assert _commands(c) == [
        "docformatter --config ./pyproject.toml --in-place --wrap-summaries 80 src/mypkg"
    ]
