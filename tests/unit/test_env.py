from __future__ import annotations

import importlib.util
import shutil
from importlib.machinery import ModuleSpec
from typing import TYPE_CHECKING

import pytest
from invoke.exceptions import Exit

from invoke_tasklib import env
from invoke_tasklib.runner import PROGRAM_HINTS
from tests.helpers import commands, make_context, run_kwargs

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


def test_create_venv_uses_configured_python_version() -> None:
    c = make_context({"package": {"name": "mypkg", "python_version": "3.11"}})
    env.create_venv(c)
    assert commands(c) == ["uv venv --python 3.11 --clear", "uv pip install invoke"]


def test_install_default_options() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.install(c)
    assert commands(c) == ["uv sync --locked --all-extras --group dev"]


def test_install_groups_from_config_list() -> None:
    c = make_context({"package": {"name": "mypkg"}, "groups": {"install": ["dev", "test"]}})
    env.install(c)
    assert commands(c) == ["uv sync --locked --all-extras --group dev --group test"]


def test_install_default_groups_from_config() -> None:
    c = make_context({"package": {"name": "mypkg"}, "groups": {"install": "dev,test"}})
    env.install(c)
    assert commands(c) == ["uv sync --locked --all-extras --group dev --group test"]


def test_install_quotes_the_groups() -> None:
    c = make_context()
    env.install(c, groups="dev;echo INJECTED")
    assert commands(c) == ["uv sync --locked --all-extras --group 'dev;echo INJECTED'"]


def test_install_no_optional_no_groups() -> None:
    c = make_context()
    env.install(c, optional_deps=False, groups="")
    assert commands(c) == ["uv sync --locked"]


def test_install_with_explicit_groups() -> None:
    c = make_context()
    env.install(c, groups="dev,docs")
    assert commands(c) == ["uv sync --locked --all-extras --group dev --group docs"]


def test_install_installs_a_duplicate_group_once() -> None:
    c = make_context()
    env.install(c, groups="dev,dev")
    assert commands(c) == ["uv sync --locked --all-extras --group dev"]


def test_install_keeps_the_order_of_the_groups_without_duplicates() -> None:
    c = make_context()
    env.install(c, groups="docs,dev,docs")
    assert commands(c) == ["uv sync --locked --all-extras --group docs --group dev"]


def test_install_with_custom_groups() -> None:
    c = make_context()
    env.install(c, groups="dev, test, lint")
    assert commands(c) == ["uv sync --locked --all-extras --group dev --group test --group lint"]


@pytest.mark.usefixtures("_pre_commit_config")
def test_update_runs_expected_commands() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.update(c)
    assert commands(c) == [
        "uv lock --upgrade",
        "pre-commit autoupdate",
        "uv sync --locked --all-extras --group dev --group docs",
    ]


@pytest.mark.usefixtures("_pre_commit_config")
def test_update_default_groups_from_config() -> None:
    c = make_context({"package": {"name": "mypkg"}, "groups": {"update": "dev,test"}})
    env.update(c)
    assert commands(c) == [
        "uv lock --upgrade",
        "pre-commit autoupdate",
        "uv sync --locked --all-extras --group dev --group test",
    ]


@pytest.mark.usefixtures("_pre_commit_config")
def test_update_with_explicit_groups() -> None:
    c = make_context()
    env.update(c, groups="dev,test")
    assert commands(c) == [
        "uv lock --upgrade",
        "pre-commit autoupdate",
        "uv sync --locked --all-extras --group dev --group test",
    ]


def test_show_installed_packages() -> None:
    c = make_context()
    env.show_installed_packages(c)
    assert commands(c) == ["uv pip list"]


def test_show_python_config() -> None:
    c = make_context()
    env.show_python_config(c)
    assert commands(c) == [
        "uv python list --only-installed",
        "uv python find",
        "command -v python",
    ]


def test_show_python_config_tolerates_a_missing_python_on_the_path() -> None:
    c = make_context()
    env.show_python_config(c)
    assert run_kwargs(c)[-1]["warn"] is True


def test_show_python_config_other_commands_must_succeed() -> None:
    c = make_context()
    env.show_python_config(c)
    assert [kwargs.get("warn", False) for kwargs in run_kwargs(c)] == [False, False, True]


############################################
#     Tests for the lock file handling     #
############################################


def test_install_requires_an_up_to_date_lock_file() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.install(c)
    assert commands(c)[0].startswith("uv sync --locked")


def test_update_without_pre_commit_config_skips_the_hooks() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.update(c)
    assert commands(c) == [
        "uv lock --upgrade",
        "uv sync --locked --all-extras --group dev --group docs",
    ]


def test_update_without_pre_commit_config_says_it_skips_the_hooks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    env.update(make_context({"package": {"name": "mypkg"}}))
    assert "⏭️  No .pre-commit-config.yaml file: skipping the pre-commit hooks" in (
        capsys.readouterr().out
    )


@pytest.mark.usefixtures("_pre_commit_config")
def test_update_with_pre_commit_config_updates_the_hooks() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.update(c)
    assert "pre-commit autoupdate" in commands(c)


def test_update_does_not_upgrade_the_uv_tools_of_the_machine() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.update(c)
    assert not any(cmd.startswith("uv tool") for cmd in commands(c))


def test_install_does_not_reinstall_the_package_outside_the_lock_file() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.install(c)
    assert not any(cmd.startswith("uv pip") for cmd in commands(c))


def test_update_locks_before_syncing() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.update(c)
    assert commands(c)[0] == "uv lock --upgrade"


def test_update_does_not_sync_twice() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.update(c)
    assert len([cmd for cmd in commands(c) if cmd.startswith("uv sync")]) == 1


###############################
#     Tests for _find_tool    #
###############################


def test_find_tool_program_found_returns_its_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: f"/bin/{name}")
    assert env._find_tool("ruff") == "/bin/ruff"


def test_find_tool_program_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert env._find_tool("ruff") is None


def test_find_tool_program_is_not_looked_up_as_a_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert env._find_tool("json") is None


def test_find_tool_module_found_returns_its_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = ModuleSpec("pytest", None, origin="/site/pytest/__init__.py")
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: spec)
    assert env._find_tool("pytest", module=True) == "/site/pytest/__init__.py"


def test_find_tool_module_without_origin_returns_its_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: ModuleSpec("pytest", None))
    assert env._find_tool("pytest", module=True) == "pytest"


def test_find_tool_module_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: None)
    assert env._find_tool("pytest", module=True) is None


def test_find_tool_module_is_not_looked_up_as_a_program(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: None)
    assert env._find_tool("ruff", module=True) is None


#################################
#     Tests for check_tools     #
#################################


@pytest.fixture
def _two_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Limit the tools to one program and one module."""
    monkeypatch.setattr(env, "TOOL_PROGRAMS", ("ruff",))
    monkeypatch.setattr(env, "TOOL_MODULES", ("pytest",))


def _available(*names: str) -> object:
    r"""Return a stand-in of ``_find_tool`` for the given names."""

    def find(name: str, **_: bool) -> str | None:
        return f"/found/{name}" if name in names else None

    return find


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_all_available_lists_every_tool(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(env, "_find_tool", _available("ruff", "pytest"))
    env.check_tools(make_context())
    assert capsys.readouterr().out == (
        "🧰 Checking the tools of the tasks...\n"
        "✅ ruff: /found/ruff\n"
        "✅ pytest: /found/pytest\n"
        "✅ All the 2 tools are available\n"
    )


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_missing_program_says_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(env, "_find_tool", _available("pytest"))
    with pytest.raises(Exit, match=r"1 of 2 tool\(s\) missing: ruff"):
        env.check_tools(make_context())
    assert capsys.readouterr().out == (
        "🧰 Checking the tools of the tasks...\n"
        "❌ ruff: program not found. Install the project tools with `invoke env.install` "
        "(see the troubleshooting page of the documentation).\n"
        "✅ pytest: /found/pytest\n"
    )


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_missing_module_says_it_is_a_python_module(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(env, "_find_tool", _available("ruff"))
    with pytest.raises(Exit, match=r"1 of 2 tool\(s\) missing: pytest"):
        env.check_tools(make_context())
    assert "❌ pytest: Python module not found." in capsys.readouterr().out


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_lists_all_the_missing_tools_not_only_the_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(env, "_find_tool", _available())
    with pytest.raises(Exit, match=r"2 of 2 tool\(s\) missing: ruff, pytest"):
        env.check_tools(make_context())


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_missing_tool_exits_with_code_127(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(env, "_find_tool", _available())
    with pytest.raises(Exit) as excinfo:
        env.check_tools(make_context())
    assert excinfo.value.code == 127


def test_check_tools_uses_the_hint_of_the_program(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(env, "_find_tool", _available())
    with pytest.raises(Exit, match=r"tool\(s\) missing"):
        env.check_tools(make_context())
    assert f"❌ uv: program not found. {PROGRAM_HINTS['uv']}" in capsys.readouterr().out


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_looks_the_module_up_as_a_module(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    def find(name: str, *, module: bool = False) -> str:
        calls.append((name, module))
        return name

    monkeypatch.setattr(env, "_find_tool", find)
    env.check_tools(make_context())
    assert calls == [("ruff", False), ("pytest", True)]


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_does_not_run_any_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(env, "_find_tool", _available("ruff", "pytest"))
    c = make_context()
    env.check_tools(c)
    assert commands(c) == []


def test_check_tools_does_not_need_the_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(env, "_find_tool", _available(*env.TOOL_PROGRAMS, *env.TOOL_MODULES))
    env.check_tools(make_context())


def test_every_program_with_a_hint_is_checked() -> None:
    assert set(PROGRAM_HINTS) <= set(env.TOOL_PROGRAMS)
