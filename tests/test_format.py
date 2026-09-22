from __future__ import annotations

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import format  # noqa: A004


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    return [call.args[0] for call in c.run.call_args_list]


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
    find_sh = "find . -name '*.sh' -type f -not -path './.git/*'"
    assert _commands(c) == [f"{find_sh} -print0 | xargs -0 -r shellcheck --"]


def test_fix_shell() -> None:
    c = _context()
    format.fix_shell(c)
    find_sh = "find . -name '*.sh' -type f -not -path './.git/*'"
    assert _commands(c) == [f"{find_sh} -print0 | xargs -0 -r shfmt -l -w --"]
