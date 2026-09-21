from __future__ import annotations

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import release


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    return [call.args[0] for call in c.run.call_args_list]


def test_build() -> None:
    c = _context({"package": {"name": "mypkg"}})
    release.build(c)
    commands = _commands(c)
    assert "uv build" in commands
    assert (
        'uv run --with mypkg --refresh-package mypkg --no-project -- python -c "import mypkg"'
        in commands
    )


def test_pypi() -> None:
    c = _context({"package": {"name": "mypkg"}})
    release.pypi(c)
    commands = _commands(c)
    assert "uv build" in commands
    assert "uv publish --token ${PYPI_TOKEN}" in commands
