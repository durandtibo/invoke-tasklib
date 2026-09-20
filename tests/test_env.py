from __future__ import annotations

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import env


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    return [call.args[0] for call in c.run.call_args_list]


def test_create_venv_uses_configured_python_version() -> None:
    c = _context({"package": {"name": "mypkg", "python_version": "3.11"}})
    env.create_venv(c)
    commands = _commands(c)
    assert "uv venv --python 3.11 --clear" in commands
    assert "source .venv/bin/activate" in commands
    assert "uv tool install invoke" in commands


def test_install_default_options() -> None:
    c = _context()
    env.install(c)
    commands = _commands(c)
    assert "uv sync --frozen --all-extras --group dev" in commands
    assert "uv pip install -e ." in commands


def test_install_no_optional_no_dev_deps() -> None:
    c = _context()
    env.install(c, optional_deps=False, dev_deps=False)
    commands = _commands(c)
    assert "uv sync --frozen" in commands


def test_install_with_docs_deps() -> None:
    c = _context()
    env.install(c, docs_deps=True)
    commands = _commands(c)
    assert "uv sync --frozen --all-extras --group dev --group docs" in commands


def test_update_runs_expected_commands() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.update(c)
    commands = _commands(c)
    assert "uv sync --upgrade" in commands
    assert "uv tool upgrade --all" in commands
    assert "pre-commit autoupdate" in commands
    assert "uv pip install -e ." in commands


def test_show_installed_packages() -> None:
    c = _context()
    env.show_installed_packages(c)
    assert "uv pip list" in _commands(c)


def test_show_python_config() -> None:
    c = _context()
    env.show_python_config(c)
    commands = _commands(c)
    assert "uv python list --only-installed" in commands
    assert "uv python find" in commands
    assert "which python" in commands
