from __future__ import annotations

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import format


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    return [call.args[0] for call in c.run.call_args_list]


def test_check_format() -> None:
    c = _context()
    format.check_format(c)
    assert "ruff format --check ." in _commands(c)


def test_docformat_uses_configured_src_path() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"src": "src/mypkg"}})
    format.docformat(c)
    assert "docformatter --config ./pyproject.toml --in-place src/mypkg" in _commands(c)


def test_format_shell() -> None:
    c = _context()
    format.format_shell(c)
    commands = _commands(c)
    find_sh = "find . -name '*.sh' -type f -not -path './.git/*'"
    assert f"{find_sh} -print0 | xargs -0 -r shellcheck --" in commands
    assert f"{find_sh} -print0 | xargs -0 -r shfmt -l -w --" in commands
