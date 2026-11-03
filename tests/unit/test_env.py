from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import env

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r"""Run in an empty project, so the tests do not depend on the files
    of this repository."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def _pre_commit_config(_project: Path) -> None:
    (_project / ".pre-commit-config.yaml").write_text("repos: []\n")


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


def test_create_venv_uses_configured_python_version() -> None:
    c = _context({"package": {"name": "mypkg", "python_version": "3.11"}})
    env.create_venv(c)
    assert _commands(c) == ["uv venv --python 3.11 --clear", "uv pip install invoke"]


def test_install_default_options() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.install(c)
    assert _commands(c) == ["uv sync --locked --all-extras --group dev"]


def test_install_groups_from_config_list() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": ["dev", "test"]}})
    env.install(c)
    assert _commands(c) == ["uv sync --locked --all-extras --group dev --group test"]


def test_install_default_groups_from_config() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": "dev,test"}})
    env.install(c)
    assert _commands(c) == ["uv sync --locked --all-extras --group dev --group test"]


def test_install_quotes_the_groups() -> None:
    c = _context()
    env.install(c, groups="dev;echo INJECTED")
    assert _commands(c) == ["uv sync --locked --all-extras --group 'dev;echo INJECTED'"]


def test_install_no_optional_no_groups() -> None:
    c = _context()
    env.install(c, optional_deps=False, groups="")
    assert _commands(c) == ["uv sync --locked"]


def test_install_with_explicit_groups() -> None:
    c = _context()
    env.install(c, groups="dev,docs")
    assert _commands(c) == ["uv sync --locked --all-extras --group dev --group docs"]


def test_install_with_custom_groups() -> None:
    c = _context()
    env.install(c, groups="dev, test, lint")
    assert _commands(c) == ["uv sync --locked --all-extras --group dev --group test --group lint"]


@pytest.mark.usefixtures("_pre_commit_config")
def test_update_runs_expected_commands() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.update(c)
    assert _commands(c) == [
        "uv lock --upgrade",
        "pre-commit autoupdate",
        "uv sync --locked --all-extras --group dev --group docs",
    ]


@pytest.mark.usefixtures("_pre_commit_config")
def test_update_default_groups_from_config() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"update": "dev,test"}})
    env.update(c)
    assert _commands(c) == [
        "uv lock --upgrade",
        "pre-commit autoupdate",
        "uv sync --locked --all-extras --group dev --group test",
    ]


@pytest.mark.usefixtures("_pre_commit_config")
def test_update_with_explicit_groups() -> None:
    c = _context()
    env.update(c, groups="dev,test")
    assert _commands(c) == [
        "uv lock --upgrade",
        "pre-commit autoupdate",
        "uv sync --locked --all-extras --group dev --group test",
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
        "command -v python",
    ]


############################################
#     Tests for the lock file handling     #
############################################


def test_install_requires_an_up_to_date_lock_file() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.install(c)
    assert _commands(c)[0].startswith("uv sync --locked")


def test_update_without_pre_commit_config_skips_the_hooks() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.update(c)
    assert _commands(c) == [
        "uv lock --upgrade",
        "uv sync --locked --all-extras --group dev --group docs",
    ]


def test_update_without_pre_commit_config_says_it_skips_the_hooks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    env.update(_context({"package": {"name": "mypkg"}}))
    assert "⏭️  No .pre-commit-config.yaml file: skipping the pre-commit hooks" in (
        capsys.readouterr().out
    )


@pytest.mark.usefixtures("_pre_commit_config")
def test_update_with_pre_commit_config_updates_the_hooks() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.update(c)
    assert "pre-commit autoupdate" in _commands(c)


def test_update_does_not_upgrade_the_uv_tools_of_the_machine() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.update(c)
    assert not any(cmd.startswith("uv tool") for cmd in _commands(c))


def test_install_does_not_reinstall_the_package_outside_the_lock_file() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.install(c)
    assert not any(cmd.startswith("uv pip") for cmd in _commands(c))


def test_update_locks_before_syncing() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.update(c)
    assert _commands(c)[0] == "uv lock --upgrade"


def test_update_does_not_sync_twice() -> None:
    c = _context({"package": {"name": "mypkg"}})
    env.update(c)
    assert len([cmd for cmd in _commands(c) if cmd.startswith("uv sync")]) == 1
