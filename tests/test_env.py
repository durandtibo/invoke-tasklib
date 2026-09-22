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
    assert _commands(c) == ["uv venv --python 3.11 --clear", "uv tool install invoke"]


def test_install_default_options() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.install(c)
    assert _commands(c) == ["uv sync --frozen --all-extras --group dev", "uv pip install -e ."]


def test_install_default_groups_from_config() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": "dev,test"}})
    env.install(c)
    assert _commands(c) == [
        "uv sync --frozen --all-extras --group dev --group test",
        "uv pip install -e .",
    ]


def test_install_no_optional_no_groups() -> None:
    c = _context()
    env.install(c, optional_deps=False, groups="")
    assert _commands(c) == ["uv sync --frozen", "uv pip install -e ."]


def test_install_with_explicit_groups() -> None:
    c = _context()
    env.install(c, groups="dev,docs")
    assert _commands(c) == [
        "uv sync --frozen --all-extras --group dev --group docs",
        "uv pip install -e .",
    ]


def test_install_with_custom_groups() -> None:
    c = _context()
    env.install(c, groups="dev, test, lint")
    assert _commands(c) == [
        "uv sync --frozen --all-extras --group dev --group test --group lint",
        "uv pip install -e .",
    ]


def test_update_runs_expected_commands() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.update(c)
    assert _commands(c) == [
        "uv sync --upgrade",
        "uv tool upgrade --all",
        "pre-commit autoupdate",
        "uv sync --frozen --all-extras --group dev --group docs",
        "uv pip install -e .",
    ]


def test_update_default_groups_from_config() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"update": "dev,test"}})
    env.update(c)
    assert _commands(c) == [
        "uv sync --upgrade",
        "uv tool upgrade --all",
        "pre-commit autoupdate",
        "uv sync --frozen --all-extras --group dev --group test",
        "uv pip install -e .",
    ]


def test_show_installed_packages() -> None:
    c = _context()
    env.show_installed_packages(c)
    assert _commands(c) == ["uv pip list"]


def test_show_python_config() -> None:
    c = _context()
    env.show_python_config(c)
    assert _commands(c) == [
        "uv python list --only-installed",
        "uv python find",
        "which python",
    ]
