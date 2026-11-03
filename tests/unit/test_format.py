from __future__ import annotations

from unittest.mock import Mock

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import format  # noqa: A004


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


def test_check_python() -> None:
    c = _context()
    format.check_python(c)
    assert _commands(c) == ["ruff format --check ."]


def test_check_docstrings_uses_configured_src_path() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"src": "src/mypkg"}})
    format.check_docstrings(c)
    assert _commands(c) == ["docformatter --config ./pyproject.toml --check src/mypkg"]


def test_fix_python() -> None:
    c = _context()
    format.fix_python(c)
    assert _commands(c) == ["ruff format ."]


def test_fix_docstrings_uses_configured_src_path() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"src": "src/mypkg"}})
    format.fix_docstrings(c)
    assert _commands(c) == ["docformatter --config ./pyproject.toml --in-place src/mypkg"]


def test_check_shell() -> None:
    c = _context()
    format.check_shell(c)
    assert _commands(c) == [f"{format._FIND_SH} | xargs -0 -r shellcheck --"]


def test_fix_shell() -> None:
    c = _context()
    format.fix_shell(c)
    assert _commands(c) == [f"{format._FIND_SH} | xargs -0 -r shfmt -l -w --"]


##############################
#     Tests for _FIND_SH     #
##############################


def test_find_sh_command() -> None:
    assert format._FIND_SH == (
        "find . \\( -name .git -o -name .pytest_cache -o -name .venv -o -name build "
        "-o -name dist -o -name node_modules -o -name site \\) -type d -prune "
        "-o -name '*.sh' -type f -print0"
    )
