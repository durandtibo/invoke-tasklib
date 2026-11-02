from __future__ import annotations

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import release


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    return [call.args[0] for call in c.run.call_args_list]


_INSTALL_CHECK_CMD = (
    'uv run --with mypkg --refresh-package mypkg --no-project -- python -c "import mypkg"'
)


def test_build_without_check() -> None:
    c = _context({"package": {"name": "mypkg"}})
    release.build(c)
    assert _commands(c) == ["uv build", _INSTALL_CHECK_CMD]


def test_build_with_check() -> None:
    c = _context({"package": {"name": "mypkg"}})
    release.build(c, check=True)
    assert _commands(c) == ["uv build", _INSTALL_CHECK_CMD, "uvx twine check dist/*"]


def test_pypi() -> None:
    c = _context({"package": {"name": "mypkg"}})
    release.pypi(c)
    assert _commands(c) == [
        "uv build",
        _INSTALL_CHECK_CMD,
        "uv publish --token ${PYPI_TOKEN}",
    ]
