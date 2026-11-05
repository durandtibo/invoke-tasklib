from __future__ import annotations

import importlib.util
import re
import shutil
import sys
from importlib.machinery import ModuleSpec
from typing import TYPE_CHECKING

import pytest
from invoke.exceptions import Exit

from invoke_tasklib.runner import build_command
from invoke_tasklib.tools import (
    DEFAULT_HINT,
    MODULE_GROUPS,
    PLUGIN_OPTIONS,
    PROGRAM_GROUPS,
    PROGRAM_HINTS,
    TOOLS,
    Tool,
    _check_module,
    _check_plugin_options,
    _strip_assignments,
    _system_hint,
    check_program,
    find_tool,
    hint,
    not_found_message,
    tool_path,
)

if TYPE_CHECKING:
    from collections.abc import Callable

###################################
#     Tests for check_program     #
###################################


def test_check_program_accepts_a_program_on_the_path() -> None:
    assert check_program("ruff check .") is None


def test_check_program_missing_program_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", lambda _program, **_kwargs: None)
    with pytest.raises(
        Exit,
        match=r"'ruff' was not found on the PATH or next to the Python interpreter.*'dev' group",
    ):
        check_program("ruff --version")


@pytest.mark.parametrize(
    ("program", "group"),
    [("ruff", "dev"), ("ty", "dev"), ("pre-commit", "dev"), ("mkdocs", "docs"), ("mike", "docs")],
)
def test_check_program_names_the_group_of_a_tool(
    monkeypatch: pytest.MonkeyPatch, program: str, group: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only())
    with pytest.raises(Exit, match=rf"'{group}' group: `uv sync --group {group}`"):
        check_program(f"{program} --version")


def test_check_program_missing_program_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", lambda _program, **_kwargs: None)
    with pytest.raises(Exit, match=r"'no-such-program' was not found") as excinfo:
        check_program("no-such-program --version")
    assert excinfo.value.code == 127


@pytest.mark.parametrize(
    "command", ["command -v python", "cd docs", "export FOO=1", "test -d docs", "[ -d docs ]"]
)
def test_check_program_skips_unchecked_programs(
    command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", lambda _program, **_kwargs: None)
    assert check_program(command) is None


def test_check_program_skips_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", lambda _program, **_kwargs: None)
    assert check_program("/usr/bin/python -m pytest") is None


def test_check_program_skips_empty_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", lambda _program, **_kwargs: None)
    assert check_program("") is None


def test_check_program_quoted_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", lambda _program, **_kwargs: None)
    assert check_program("'/path with space/python' -m pytest") is None


@pytest.mark.parametrize(
    "command",
    [
        "FOO=1 ruff check",
        "FOO=1 BAR=2 ruff check",
        "FOO= ruff check",
        "VAR=$(date) ruff check",
        "exec ruff check",
        "source env.sh",
        ". env.sh",
        ": && ruff check",
        "FOO=1",
        "~/bin/tool --version",
        "./run.sh",
        "bin/tool --version",
    ],
)
def test_check_program_accepts_valid_forms(monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only("ruff"))
    assert check_program(command) is None


def test_check_program_still_checks_the_program_after_an_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only())
    with pytest.raises(Exit, match=r"^'ruff' was not found on the PATH"):
        check_program("FOO=1 ruff check")


@pytest.mark.parametrize("command", ["sudo ruff check", "time ruff check", "env FOO=1 ruff check"])
def test_check_program_checks_the_first_word_of_a_wrapper(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only())
    with pytest.raises(Exit, match=rf"^'{command.split(maxsplit=1)[0]}' was not found on the PATH"):
        check_program(command)


@pytest.mark.parametrize("command", ["sudo ruff check", "time ruff check", "env FOO=1 ruff check"])
def test_check_program_does_not_look_past_a_wrapper(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only("sudo", "time", "env"))
    assert check_program(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "ls | no-such-program",
        "ls && no-such-program",
        "ls ; no-such-program",
        "ls & no-such-program",
    ],
)
def test_check_program_only_checks_the_first_word(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only("ls"))
    assert check_program(command) is None


@pytest.mark.parametrize(
    "command", ["(ls)", "{ ls; }", "$(echo ls)", "if true; then ls; fi", "! ls"]
)
def test_check_program_looks_up_the_first_word_of_a_shell_form(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only())
    with pytest.raises(Exit, match=r"was not found on the PATH"):
        check_program(command)


def test_check_program_does_not_take_a_quoted_separator_for_a_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only("ls"))
    assert check_program("ls ';' foo") is None


def test_check_program_does_not_check_the_arguments_built_by_build_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only("ls"))
    assert check_program(build_command("ls", args="-k ';' x")) is None


@pytest.mark.parametrize("command", ["ls 'unclosed", 'ls "unclosed'])
def test_check_program_does_not_check_a_command_that_cannot_be_split(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only())
    assert check_program(command) is None


def test_check_program_find_is_looked_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only())
    with pytest.raises(Exit, match=r"^'find' was not found on the PATH"):
        check_program("find . -name x")


###########################################
#     Tests for the hints of programs     #
###########################################


def _only(*available: str) -> Callable[..., str | None]:
    return lambda program, **_kwargs: f"/bin/{program}" if program in available else None


@pytest.mark.parametrize("program", ["uv", "uvx", "git", "shellcheck", "shfmt", "codespell"])
def test_check_program_uses_the_hint_of_the_program(
    monkeypatch: pytest.MonkeyPatch, program: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only())
    with pytest.raises(Exit, match=re.escape(PROGRAM_HINTS[program])):
        check_program(f"{program} --version")


def test_check_program_uv_hint_does_not_suggest_env_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only())
    with pytest.raises(
        Exit,
        match=r"^'uv' was not found on the PATH or next to the Python interpreter\. Install uv, see https://",
    ):
        check_program("uv sync")


def test_check_program_unknown_program_uses_the_default_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", _only())
    with pytest.raises(Exit, match=re.escape(DEFAULT_HINT)):
        check_program("no-such-program --version")


def test_check_program_missing_module_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.sys.executable", "/venv/bin/python")
    monkeypatch.setattr(
        "invoke_tasklib.tools.importlib.util.find_spec", lambda _name, **_kwargs: None
    )
    with pytest.raises(
        Exit, match=r"The Python module 'pytest' is not installed for /venv/bin/python"
    ):
        check_program("/venv/bin/python -m pytest tests")


def test_check_program_missing_module_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.sys.executable", "/venv/bin/python")
    monkeypatch.setattr(
        "invoke_tasklib.tools.importlib.util.find_spec", lambda _name, **_kwargs: None
    )
    with pytest.raises(Exit, match=r"module 'pytest' is not installed") as excinfo:
        check_program("/venv/bin/python -m pytest tests")
    assert excinfo.value.code == 127


def test_check_program_missing_module_after_an_assignment_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.sys.executable", "/venv/bin/python")
    monkeypatch.setattr(
        "invoke_tasklib.tools.importlib.util.find_spec", lambda _name, **_kwargs: None
    )
    with pytest.raises(Exit, match=r"The Python module 'coverage' is not installed"):
        check_program("FOO=1 /venv/bin/python -m coverage report")


###################################
#     Tests for _check_module     #
###################################


def test_check_module_accepts_an_installed_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.sys.executable", "/venv/bin/python")
    assert _check_module(["/venv/bin/python", "-m", "pytest"]) is None


def test_check_module_ignores_another_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.sys.executable", "/venv/bin/python")
    monkeypatch.setattr(
        "invoke_tasklib.tools.importlib.util.find_spec", lambda _name, **_kwargs: None
    )
    assert _check_module(["/other/python", "-m", "pytest"]) is None


@pytest.mark.parametrize(
    "words", [["/venv/bin/python"], ["/venv/bin/python", "-m"], ["/venv/bin/python", "-c", "pass"]]
)
def test_check_module_ignores_a_command_that_is_not_a_module_run(
    monkeypatch: pytest.MonkeyPatch, words: list[str]
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.sys.executable", "/venv/bin/python")
    monkeypatch.setattr(
        "invoke_tasklib.tools.importlib.util.find_spec", lambda _name, **_kwargs: None
    )
    assert _check_module(words) is None


def test_check_module_missing_module_uses_the_default_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.sys.executable", "/venv/bin/python")
    monkeypatch.setattr(
        "invoke_tasklib.tools.importlib.util.find_spec", lambda _name, **_kwargs: None
    )
    with pytest.raises(Exit, match=re.escape(DEFAULT_HINT)):
        _check_module(["/venv/bin/python", "-m", "no_such_module_xyz"])


def test_check_module_missing_module_names_its_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.sys.executable", "/venv/bin/python")
    monkeypatch.setattr(
        "invoke_tasklib.tools.importlib.util.find_spec", lambda _name, **_kwargs: None
    )
    with pytest.raises(Exit, match=r"'dev' group: `uv sync --group dev`"):
        _check_module(["/venv/bin/python", "-m", "pytest"])


##########################
#     Tests for hint     #
##########################


def test_hint_known_program() -> None:
    assert hint("shfmt") == PROGRAM_HINTS["shfmt"]


def test_hint_program_of_a_group() -> None:
    assert hint("mike") == "Install it with the 'docs' group: `uv sync --group docs`."


def test_hint_unknown_program() -> None:
    assert hint("no-such-program") == DEFAULT_HINT


def test_hint_explicit_entry_wins_over_the_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(PROGRAM_GROUPS, "uv", "dev")
    assert hint("uv") == PROGRAM_HINTS["uv"]


def test_hint_module_of_a_group() -> None:
    assert hint("pytest", module=True) == "Install it with the 'dev' group: `uv sync --group dev`."


def test_hint_unknown_module() -> None:
    assert hint("no_such_module", module=True) == DEFAULT_HINT


def test_hint_module_name_is_not_looked_up_as_a_program() -> None:
    assert hint("pytest") == DEFAULT_HINT


def test_hint_program_name_is_not_looked_up_as_a_module() -> None:
    assert hint("ruff", module=True) == DEFAULT_HINT


def test_hint_module_ignores_the_hint_of_a_program(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(PROGRAM_HINTS, "pytest", "program hint")
    assert hint("pytest", module=True) == "Install it with the 'dev' group: `uv sync --group dev`."


def test_hint_module_uses_the_module_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(MODULE_GROUPS, "special", "extra")
    assert (
        hint("special", module=True)
        == "Install it with the 'extra' group: `uv sync --group extra`."
    )


def test_hint_of_pytest_benchmark_names_its_group() -> None:
    assert hint("pytest_benchmark", module=True) == (
        "Install it with the 'dev' group: `uv sync --group dev`."
    )


def test_every_plugin_module_has_a_group() -> None:
    assert {module for module, _ in PLUGIN_OPTIONS.values()} <= set(MODULE_GROUPS)


def test_program_and_module_groups_do_not_share_a_name() -> None:
    assert set(PROGRAM_GROUPS) & set(MODULE_GROUPS) == set()


@pytest.mark.parametrize("program", ["uvx", "git", "pre-commit"])
def test_hint_is_not_the_default_for_a_program_env_install_cannot_provide(program: str) -> None:
    assert hint(program) != DEFAULT_HINT


def _missing(*modules: str) -> Callable[[str], object | None]:
    return lambda name, **_kwargs: None if name in modules else object()


@pytest.fixture
def _venv_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.sys.executable", "/venv/bin/python")


@pytest.mark.usefixtures("_venv_python")
@pytest.mark.parametrize(
    ("word", "option", "module", "package"),
    [
        ("--xdoctest", "--xdoctest", "xdoctest", "xdoctest"),
        ("--timeout=10", "--timeout", "pytest_timeout", "pytest-timeout"),
        ("--cov=mypkg", "--cov", "pytest_cov", "pytest-cov"),
        ("--benchmark-only", "--benchmark-only", "pytest_benchmark", "pytest-benchmark"),
        ("--benchmark-compare", "--benchmark-compare", "pytest_benchmark", "pytest-benchmark"),
        ("--benchmark-disable", "--benchmark-disable", "pytest_benchmark", "pytest-benchmark"),
        ("--no-cov", "--no-cov", "pytest_cov", "pytest-cov"),
        ("--cov-branch", "--cov-branch", "pytest_cov", "pytest-cov"),
        ("--cov-config=x.toml", "--cov-config", "pytest_cov", "pytest-cov"),
    ],
)
def test_check_module_missing_pytest_plugin_names_the_package(
    monkeypatch: pytest.MonkeyPatch, word: str, option: str, module: str, package: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.importlib.util.find_spec", _missing(module))
    with pytest.raises(Exit, match=rf"^The option {option} needs .*'{package}'"):
        _check_module(["/venv/bin/python", "-m", "pytest", word, "tests"])


@pytest.mark.usefixtures("_venv_python")
def test_check_module_missing_pytest_plugin_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.importlib.util.find_spec", _missing("xdoctest"))
    with pytest.raises(Exit, match=r"The option --xdoctest needs the pytest plugin") as info:
        _check_module(["/venv/bin/python", "-m", "pytest", "--xdoctest", "src"])
    assert str(info.value) == (
        "The option --xdoctest needs the pytest plugin 'xdoctest', which is not installed "
        "for /venv/bin/python. Add it to the dependencies of the project, "
        "e.g. `uv add --dev xdoctest`."
    )


@pytest.mark.usefixtures("_venv_python")
def test_check_module_missing_pytest_plugin_exits_with_code_127(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.importlib.util.find_spec", _missing("xdoctest"))
    with pytest.raises(Exit, match=r"xdoctest") as info:
        _check_module(["/venv/bin/python", "-m", "pytest", "--xdoctest"])
    assert info.value.code == 127


@pytest.mark.usefixtures("_venv_python")
def test_check_module_accepts_an_installed_pytest_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "invoke_tasklib.tools.importlib.util.find_spec", lambda _name, **_kwargs: object()
    )
    assert _check_module(["/venv/bin/python", "-m", "pytest", "--xdoctest"]) is None


@pytest.mark.usefixtures("_venv_python")
def test_check_module_missing_pytest_reports_pytest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "invoke_tasklib.tools.importlib.util.find_spec", _missing("pytest", "xdoctest")
    )
    with pytest.raises(Exit, match=r"^The Python module 'pytest' is not installed"):
        _check_module(["/venv/bin/python", "-m", "pytest", "--xdoctest"])


@pytest.mark.usefixtures("_venv_python")
def test_check_module_does_not_check_plugin_options_of_another_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.importlib.util.find_spec", _missing("xdoctest"))
    assert _check_module(["/venv/bin/python", "-m", "coverage", "--xdoctest"]) is None


###########################################
#     Tests for _check_plugin_options     #
###########################################


def test_check_plugin_options_ignores_other_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.importlib.util.find_spec", _missing("xdoctest"))
    assert _check_plugin_options(["-x", "-k", "foo", "tests"]) is None


def test_check_plugin_options_no_words_is_ok() -> None:
    assert _check_plugin_options([]) is None


def test_check_plugin_options_stops_at_double_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.importlib.util.find_spec", _missing("xdoctest"))
    assert _check_plugin_options(["--", "--xdoctest"]) is None


def test_check_plugin_options_reports_the_first_missing_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "invoke_tasklib.tools.importlib.util.find_spec", _missing("xdoctest", "pytest_timeout")
    )
    with pytest.raises(Exit, match=r"^The option --timeout needs .*'pytest-timeout'"):
        _check_plugin_options(["--timeout", "5", "--xdoctest"])


def test_check_plugin_options_looks_the_module_up_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def find_spec(name: str) -> object:
        seen.append(name)
        return object()

    monkeypatch.setattr("invoke_tasklib.tools.importlib.util.find_spec", find_spec)
    _check_plugin_options(["--cov-report", "html"])
    assert seen == ["pytest_cov"]


########################################
#     Tests for _strip_assignments     #
########################################


def test_strip_assignments_removes_the_leading_assignments() -> None:
    assert _strip_assignments(["FOO=1", "BAR=", "ruff", "check"]) == ["ruff", "check"]


def test_strip_assignments_keeps_a_command_without_assignment() -> None:
    assert _strip_assignments(["ruff", "check"]) == ["ruff", "check"]


def test_strip_assignments_keeps_an_assignment_after_the_program() -> None:
    assert _strip_assignments(["env", "FOO=1", "ruff"]) == ["env", "FOO=1", "ruff"]


def test_strip_assignments_only_assignments_is_empty() -> None:
    assert _strip_assignments(["FOO=1"]) == []


def test_strip_assignments_empty_is_empty() -> None:
    assert _strip_assignments([]) == []


@pytest.mark.parametrize("word", ["--flag=1", "1A=2", "=1", "a-b=1"])
def test_strip_assignments_keeps_a_word_that_is_not_a_variable_name(word: str) -> None:
    assert _strip_assignments([word, "x"]) == [word, "x"]


def test_strip_assignments_does_not_mutate_its_input() -> None:
    words = ["FOO=1", "ruff"]
    _strip_assignments(words)
    assert words == ["FOO=1", "ruff"]


###############################
#     Tests for find_tool     #
###############################


def test_find_tool_program_found_returns_its_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name, **_kwargs: f"/bin/{name}")
    assert find_tool("ruff") == "/bin/ruff"


def test_find_tool_program_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _, **_kwargs: None)
    assert find_tool("ruff") is None


def test_find_tool_program_is_not_looked_up_as_a_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _, **_kwargs: None)
    assert find_tool("json") is None


def test_find_tool_module_found_returns_its_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = ModuleSpec("pytest", None, origin="/site/pytest/__init__.py")
    monkeypatch.setattr(importlib.util, "find_spec", lambda _, **_kwargs: spec)
    assert find_tool("pytest", module=True) == "/site/pytest/__init__.py"


def test_find_tool_module_without_origin_returns_its_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda _, **_kwargs: ModuleSpec("pytest", None)
    )
    assert find_tool("pytest", module=True) == "pytest"


def test_find_tool_module_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda _, **_kwargs: None)
    assert find_tool("pytest", module=True) is None


def test_find_tool_module_is_not_looked_up_as_a_program(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name, **_kwargs: f"/bin/{name}")
    monkeypatch.setattr(importlib.util, "find_spec", lambda _, **_kwargs: None)
    assert find_tool("ruff", module=True) is None


#######################################
#     Tests for not_found_message     #
#######################################


def test_not_found_message_for_a_program() -> None:
    assert (
        not_found_message("uv")
        == "'uv' was not found on the PATH or next to the Python interpreter. "
        f"{PROGRAM_HINTS['uv']}"
    )


def test_not_found_message_for_a_module_names_the_running_interpreter() -> None:
    assert not_found_message("pytest", module=True) == (
        f"The Python module 'pytest' is not installed for {sys.executable}. "
        f"{hint('pytest', module=True)}"
    )


def test_not_found_message_for_a_module_names_the_given_interpreter() -> None:
    assert not_found_message("pytest", module=True, interpreter="/x/python").startswith(
        "The Python module 'pytest' is not installed for /x/python. "
    )


def test_not_found_message_for_an_unknown_program_uses_the_default_hint() -> None:
    assert not_found_message("zzz").endswith(DEFAULT_HINT)


##############################
#     Tests for the TOOLS    #
##############################


def test_tool_defaults() -> None:
    assert Tool("ruff") == Tool("ruff", "program", None, None, ())


def test_tools_are_keyed_by_their_name() -> None:
    assert all(name == tool.name for name, tool in TOOLS.items())


def test_tools_programs_in_the_order_of_env_check_tools() -> None:
    assert [t.name for t in TOOLS.values() if t.kind == "program"] == [
        "uv",
        "uvx",
        "git",
        "ruff",
        "ty",
        "pyright",
        "mypy",
        "docformatter",
        "codespell",
        "pre-commit",
        "shellcheck",
        "shfmt",
        "mkdocs",
        "mike",
    ]


def test_tools_modules_in_the_order_of_env_check_tools() -> None:
    assert [t.name for t in TOOLS.values() if t.kind == "module"] == [
        "pytest",
        "coverage",
        "xdoctest",
        "pytest_timeout",
        "pytest_cov",
        "pytest_benchmark",
    ]


@pytest.mark.parametrize("tool", TOOLS.values(), ids=list(TOOLS))
def test_every_tool_has_a_group_or_a_hint(tool: Tool) -> None:
    assert (tool.group is None) != (tool.hint is None)


def test_program_groups_whole_table() -> None:
    assert PROGRAM_GROUPS == {
        "ruff": "dev",
        "ty": "dev",
        "pyright": "dev",
        "docformatter": "dev",
        "pre-commit": "dev",
        "mkdocs": "docs",
        "mike": "docs",
    }


def test_module_groups_whole_table() -> None:
    assert MODULE_GROUPS == {
        "pytest": "dev",
        "coverage": "dev",
        "xdoctest": "dev",
        "pytest_timeout": "dev",
        "pytest_cov": "dev",
        "pytest_benchmark": "dev",
    }


def test_program_hints_are_the_programs_without_a_group() -> None:
    assert sorted(PROGRAM_HINTS) == [
        "codespell",
        "git",
        "mypy",
        "shellcheck",
        "shfmt",
        "uv",
        "uvx",
    ]


def test_plugin_options_whole_table() -> None:
    assert PLUGIN_OPTIONS == {
        "--xdoctest": ("xdoctest", "xdoctest"),
        "--timeout": ("pytest_timeout", "pytest-timeout"),
        "--cov": ("pytest_cov", "pytest-cov"),
        "--cov-report": ("pytest_cov", "pytest-cov"),
        "--cov-append": ("pytest_cov", "pytest-cov"),
        "--cov-fail-under": ("pytest_cov", "pytest-cov"),
        "--cov-branch": ("pytest_cov", "pytest-cov"),
        "--cov-config": ("pytest_cov", "pytest-cov"),
        "--no-cov": ("pytest_cov", "pytest-cov"),
        "--benchmark-only": ("pytest_benchmark", "pytest-benchmark"),
        "--benchmark-compare": ("pytest_benchmark", "pytest-benchmark"),
        "--benchmark-disable": ("pytest_benchmark", "pytest-benchmark"),
    }


def test_plugin_options_are_provided_by_modules() -> None:
    assert {module for module, _ in PLUGIN_OPTIONS.values()} <= {
        t.name for t in TOOLS.values() if t.kind == "module"
    }


def test_system_hint() -> None:
    assert _system_hint("jq") == (
        "Install jq with your system package manager, for example "
        "`brew install jq` or `apt install jq`."
    )


def test_system_hint_with_an_extra_sentence() -> None:
    assert _system_hint("jq", extra=", or elsewhere").endswith("`apt install jq`, or elsewhere.")


###############################
#     Tests for tool_path     #
###############################


def test_tool_path_starts_with_the_interpreter_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert tool_path() == "/venv/bin:/usr/bin:/bin"


def test_tool_path_without_path_is_the_interpreter_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")
    monkeypatch.delenv("PATH")
    assert tool_path() == "/venv/bin"


def test_tool_path_with_empty_path_is_the_interpreter_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")
    monkeypatch.setenv("PATH", "")
    assert tool_path() == "/venv/bin"


def test_find_tool_looks_the_program_up_in_the_tool_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths: list[str | None] = []
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setattr(shutil, "which", lambda _name, path=None: paths.append(path))
    find_tool("ruff")
    assert paths == ["/venv/bin:/usr/bin"]


def test_check_program_looks_the_program_up_in_the_tool_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths: list[str | None] = []
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setattr(shutil, "which", lambda name, path=None: paths.append(path) or name)
    check_program("ruff check .")
    assert paths == ["/venv/bin:/usr/bin"]
