from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.exceptions import Exit

from invoke_tasklib import env
from invoke_tasklib.tools import DEFAULT_HINT, PROGRAM_HINTS, hint
from tests.helpers import commands, make_context, run_kwargs

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r"""Run in an empty project, so the tests do not depend on the files
    of this repository."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").write_text("")
    return tmp_path


@pytest.fixture
def _existing_venv(_project: Path) -> None:
    (_project / ".venv").mkdir()


@pytest.fixture
def _pre_commit_config(_project: Path) -> None:
    (_project / ".pre-commit-config.yaml").write_text("repos: []\n")


def test_create_venv_uses_configured_python_version() -> None:
    c = make_context({"package": {"name": "mypkg", "python_version": "3.11"}})
    env.create_venv(c)
    assert commands(c) == [
        "uv venv --python 3.11 --clear",
        "uv sync --locked --all-extras --group dev",
    ]


def test_create_venv_dry_run_runs_nothing() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.create_venv(c, dry_run=True)
    assert commands(c) == []


def test_create_venv_dry_run_names_the_configured_python_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    c = make_context({"package": {"name": "mypkg", "python_version": "3.11"}})
    env.create_venv(c, dry_run=True)
    assert capsys.readouterr().out == "🐍 Would create .venv with Python 3.11 (dry run)\n"


def test_create_venv_says_the_configured_python_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    env.create_venv(make_context({"package": {"name": "mypkg", "python_version": "3.11"}}))
    assert "🐍 Creating virtual environment with Python 3.11...\n" in capsys.readouterr().out


def test_create_venv_dry_run_says_what_it_would_do(capsys: pytest.CaptureFixture[str]) -> None:
    env.create_venv(make_context({"package": {"name": "mypkg"}}), dry_run=True)
    assert capsys.readouterr().out == "🐍 Would create .venv (dry run)\n"


@pytest.mark.usefixtures("_existing_venv")
def test_create_venv_dry_run_does_not_ask() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.create_venv(c, dry_run=True)
    assert commands(c) == []


@pytest.mark.usefixtures("_existing_venv")
def test_create_venv_asks_before_clearing_an_existing_venv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    c = make_context({"package": {"name": "mypkg"}})
    with pytest.raises(Exit, match=r"Environment '\.venv' not cleared$"):
        env.create_venv(c)


@pytest.mark.usefixtures("_existing_venv")
def test_create_venv_runs_nothing_when_the_clearing_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    c = make_context({"package": {"name": "mypkg"}})
    with pytest.raises(Exit, match=r"not cleared"):
        env.create_venv(c)
    assert commands(c) == []


@pytest.mark.usefixtures("_existing_venv")
def test_create_venv_goes_on_after_a_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    c = make_context({"package": {"name": "mypkg"}})
    env.create_venv(c)
    assert commands(c)[0] == "uv venv --clear"


@pytest.mark.usefixtures("_existing_venv")
def test_create_venv_yes_does_not_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    c = make_context({"package": {"name": "mypkg"}})
    env.create_venv(c, yes=True)
    assert commands(c)[0] == "uv venv --clear"


def test_create_venv_does_not_ask_without_an_existing_venv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    c = make_context({"package": {"name": "mypkg"}})
    env.create_venv(c)
    assert commands(c)[0] == "uv venv --clear"


def test_create_venv_without_python_version_leaves_the_choice_to_uv() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.create_venv(c)
    assert "--python" not in commands(c)[0]


def test_create_venv_installs_the_configured_groups() -> None:
    c = make_context({"package": {"name": "mypkg"}, "groups": {"install": ["dev", "docs"]}})
    env.create_venv(c)
    assert commands(c)[-1] == "uv sync --locked --all-extras --group dev --group docs"


def test_create_venv_does_not_install_invoke_alone() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.create_venv(c)
    assert "uv pip install invoke" not in commands(c)


def test_create_venv_does_not_sync_when_the_venv_cannot_be_created() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    c.run = Mock(side_effect=Exit("no uv", code=127))
    with pytest.raises(Exit, match=r"no uv"):
        env.create_venv(c)
    assert commands(c) == ["uv venv --clear"]


def test_create_venv_says_what_it_does(capsys: pytest.CaptureFixture[str]) -> None:
    env.create_venv(make_context({"package": {"name": "mypkg"}}))
    assert capsys.readouterr().out == (
        "🐍 Creating virtual environment...\n"
        "📦 Installing from uv.lock...\n"
        "✅ Installation complete\n"
        "✅ Virtual environment created successfully\n"
    )


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


#################################
#     Tests for check_tools     #
#################################


@pytest.fixture
def _two_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Limit the tools to one program and one module."""
    monkeypatch.setattr(env, "TOOL_PROGRAMS", ("ruff",))
    monkeypatch.setattr(env, "TOOL_MODULES", ("pytest",))


def _available(*names: str) -> object:
    r"""Return a stand-in of ``find_tool`` for the given names."""

    def find(name: str, **_: bool) -> str | None:
        return f"/found/{name}" if name in names else None

    return find


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_all_available_lists_every_tool(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(env, "find_tool", _available("ruff", "pytest"))
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
    monkeypatch.setattr(env, "find_tool", _available("pytest"))
    with pytest.raises(Exit, match=r"1 of 2 tool\(s\) missing: ruff"):
        env.check_tools(make_context())
    assert capsys.readouterr().out == (
        "🧰 Checking the tools of the tasks...\n"
        "❌ 'ruff' was not found on the PATH. Install it with the 'dev' group: "
        "`uv sync --group dev`.\n"
        "✅ pytest: /found/pytest\n"
    )


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_missing_module_says_it_is_a_python_module(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(env, "find_tool", _available("ruff"))
    with pytest.raises(Exit, match=r"1 of 2 tool\(s\) missing: pytest"):
        env.check_tools(make_context())
    assert "❌ The Python module 'pytest' is not installed for" in capsys.readouterr().out


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_lists_all_the_missing_tools_not_only_the_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(env, "find_tool", _available())
    with pytest.raises(Exit, match=r"2 of 2 tool\(s\) missing: ruff, pytest"):
        env.check_tools(make_context())


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_missing_tool_exits_with_code_127(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(env, "find_tool", _available())
    with pytest.raises(Exit, match=r"tool\(s\) missing") as excinfo:
        env.check_tools(make_context())
    assert excinfo.value.code == 127


def test_check_tools_uses_the_hint_of_the_program(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(env, "find_tool", _available())
    with pytest.raises(Exit, match=r"tool\(s\) missing"):
        env.check_tools(make_context())
    assert f"❌ 'uv' was not found on the PATH. {PROGRAM_HINTS['uv']}" in capsys.readouterr().out


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_looks_the_module_up_as_a_module(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    def find(name: str, *, module: bool = False) -> str:
        calls.append((name, module))
        return name

    monkeypatch.setattr(env, "find_tool", find)
    env.check_tools(make_context())
    assert calls == [("ruff", False), ("pytest", True)]


@pytest.mark.usefixtures("_two_tools")
def test_check_tools_does_not_run_any_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(env, "find_tool", _available("ruff", "pytest"))
    c = make_context()
    env.check_tools(c)
    assert commands(c) == []


def test_check_tools_does_not_need_the_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(env, "find_tool", _available(*env.TOOL_PROGRAMS, *env.TOOL_MODULES))
    env.check_tools(make_context())
    assert "✅ All the 18 tools are available\n" in capsys.readouterr().out


def test_every_program_with_a_hint_is_checked() -> None:
    assert set(PROGRAM_HINTS) <= set(env.TOOL_PROGRAMS)


@pytest.mark.parametrize("name", env.TOOL_PROGRAMS)
def test_every_checked_program_has_an_explicit_hint(name: str) -> None:
    assert hint(name) != DEFAULT_HINT


@pytest.mark.parametrize("name", env.TOOL_MODULES)
def test_every_checked_module_has_an_explicit_hint(name: str) -> None:
    assert hint(name, module=True) != DEFAULT_HINT


def test_install_reports_a_failure(capsys: pytest.CaptureFixture[str]) -> None:
    c = make_context({"package": {"name": "mypkg"}})
    c.run = Mock(side_effect=Exit("boom", code=1))
    with pytest.raises(Exit, match=r"boom"):
        env.install(c)
    assert "❌ Failed: Installing project dependencies" in capsys.readouterr().err


def test_update_reports_a_failure(capsys: pytest.CaptureFixture[str]) -> None:
    c = make_context({"package": {"name": "mypkg"}})
    c.run = Mock(side_effect=Exit("boom", code=1))
    with pytest.raises(Exit, match=r"boom"):
        env.update(c)
    assert "❌ Failed: Updating dependencies" in capsys.readouterr().err


def test_create_venv_reports_a_failure(capsys: pytest.CaptureFixture[str]) -> None:
    c = make_context({"package": {"name": "mypkg"}})
    c.run = Mock(side_effect=Exit("boom", code=1))
    with pytest.raises(Exit, match=r"boom"):
        env.create_venv(c)
    assert "❌ Failed: Creating virtual environment" in capsys.readouterr().err


def _fail_on_sync(command: str, **_kwargs: object) -> None:
    if command.startswith("uv sync"):
        msg = "boom"
        raise Exit(msg, code=1)


def test_create_venv_reports_a_failed_install_once(capsys: pytest.CaptureFixture[str]) -> None:
    c = make_context({"package": {"name": "mypkg"}})
    c.run = Mock(side_effect=_fail_on_sync)
    with pytest.raises(Exit, match=r"boom"):
        env.create_venv(c)
    assert capsys.readouterr().err == "❌ Failed: Creating virtual environment\n"


def test_update_reports_a_failed_install_once(capsys: pytest.CaptureFixture[str]) -> None:
    c = make_context({"package": {"name": "mypkg"}})
    c.run = Mock(side_effect=_fail_on_sync)
    with pytest.raises(Exit, match=r"boom"):
        env.update(c)
    assert capsys.readouterr().err == "❌ Failed: Updating dependencies\n"


def test_install_reports_a_failed_sync_once(capsys: pytest.CaptureFixture[str]) -> None:
    c = make_context({"package": {"name": "mypkg"}})
    c.run = Mock(side_effect=_fail_on_sync)
    with pytest.raises(Exit, match=r"boom"):
        env.install(c)
    assert capsys.readouterr().err == "❌ Failed: Installing project dependencies\n"


##############################
#     Tests for _install     #
##############################


def test_install_helper_runs_uv_sync_with_the_groups() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env._install(c, "dev,docs", optional_deps=True)
    assert commands(c) == ["uv sync --locked --all-extras --group dev --group docs"]


def test_install_helper_without_optional_deps() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env._install(c, "dev", optional_deps=False)
    assert commands(c) == ["uv sync --locked --group dev"]


def test_install_helper_with_no_group() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env._install(c, "", optional_deps=False)
    assert commands(c) == ["uv sync --locked"]


def test_install_helper_installs_a_repeated_group_once() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env._install(c, "dev, dev ,docs", optional_deps=False)
    assert commands(c) == ["uv sync --locked --group dev --group docs"]


def test_install_helper_quotes_a_group() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env._install(c, "a;b", optional_deps=False)
    assert commands(c) == ["uv sync --locked --group 'a;b'"]


def test_install_helper_reports_progress(capsys: pytest.CaptureFixture[str]) -> None:
    env._install(make_context({"package": {"name": "mypkg"}}), "dev", optional_deps=True)
    assert capsys.readouterr().out == ("📦 Installing from uv.lock...\n✅ Installation complete\n")


def test_install_helper_does_not_report_a_failure(capsys: pytest.CaptureFixture[str]) -> None:
    c = make_context({"package": {"name": "mypkg"}})
    c.run = Mock(side_effect=_fail_on_sync)
    with pytest.raises(Exit, match=r"boom"):
        env._install(c, "dev", optional_deps=True)
    assert "Failed" not in capsys.readouterr().err


####################################
#     Tests for _confirm_clear     #
####################################


@pytest.mark.parametrize("answer", ["y", "yes", "Y", " YES "])
def test_confirm_clear_accepts(answer: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{answer}\n"))
    assert env._confirm_clear(".venv") is None


@pytest.mark.parametrize("answer", ["", "n", "no", "maybe"])
def test_confirm_clear_refuses(answer: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{answer}\n"))
    with pytest.raises(Exit, match=r"Environment '\.venv' not cleared$"):
        env._confirm_clear(".venv")


def test_confirm_clear_refuses_without_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    with pytest.raises(Exit, match=r"not cleared: pass --yes to clear it without a terminal"):
        env._confirm_clear(".venv")


def test_confirm_clear_refuses_when_interrupted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", Mock(side_effect=KeyboardInterrupt("interrupted")))
    with pytest.raises(Exit, match=r"not cleared: pass --yes"):
        env._confirm_clear(".venv")


def test_confirm_clear_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    with pytest.raises(Exit, match=r"not cleared") as info:
        env._confirm_clear(".venv")
    assert info.value.code == 1


def test_confirm_clear_names_the_directory(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    env._confirm_clear("my-env")
    assert "Clear the existing environment 'my-env'?" in capsys.readouterr().out


#############################
#     Tests for no lock     #
#############################


@pytest.fixture
def _no_lock(_project: Path) -> None:
    (_project / "uv.lock").unlink()


@pytest.mark.usefixtures("_no_lock")
def test_install_without_lock_file_does_not_pass_locked() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.install(c)
    assert commands(c) == ["uv sync --all-extras --group dev"]


@pytest.mark.usefixtures("_no_lock")
def test_install_helper_without_lock_file_says_it_resolves(
    capsys: pytest.CaptureFixture[str],
) -> None:
    env._install(make_context({"package": {"name": "mypkg"}}), "dev", optional_deps=True)
    assert capsys.readouterr().out == (
        "📦 No uv.lock: resolving the dependencies...\n✅ Installation complete\n"
    )


@pytest.mark.usefixtures("_no_lock")
def test_create_venv_without_lock_file_does_not_pass_locked() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.create_venv(c)
    assert commands(c) == ["uv venv --clear", "uv sync --all-extras --group dev"]


@pytest.mark.usefixtures("_no_lock")
def test_update_without_lock_file_reinstalls_without_locked() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    env.update(c)
    assert commands(c)[-1] == "uv sync --all-extras --group dev --group docs"
