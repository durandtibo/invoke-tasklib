from __future__ import annotations

import importlib.util
import re
import shutil
import sys
from importlib.machinery import ModuleSpec
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit

from invoke_tasklib.runner import (
    DEFAULT_HINT,
    PROGRAM_GROUPS,
    PROGRAM_HINTS,
    _check_module,
    _check_plugin_options,
    _program_of,
    _stages,
    _strip_assignments,
    build_command,
    check_program,
    find_tool,
    hint,
    python_executable,
    run,
    split_args,
)

if TYPE_CHECKING:
    from collections.abc import Callable

#######################################
#     Tests for python_executable     #
#######################################


def test_python_executable_returns_running_interpreter() -> None:
    assert python_executable() == sys.executable


def test_python_executable_quotes_path_with_space(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/my env/bin/python")
    assert python_executable() == "'/my env/bin/python'"


#########################
#     Tests for run     #
#########################


def _context(run_config: dict | None = None) -> MockContext:
    return MockContext(config=Config(overrides={"run": run_config or {}}), run=True)


def _run_mock(c: MockContext) -> Mock:
    assert isinstance(c.run, Mock)
    return c.run


def test_run_passes_the_command() -> None:
    c = _context()
    run(c, "ls -l")
    assert _run_mock(c).call_args.args == ("ls -l",)


def test_run_echoes_the_command_by_default() -> None:
    c = _context()
    run(c, "ls")
    assert _run_mock(c).call_args.kwargs["echo"] is True


def test_run_explicit_echo_wins() -> None:
    c = _context()
    run(c, "ls", echo=False)
    assert _run_mock(c).call_args.kwargs["echo"] is False


def test_run_uses_pty_on_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    c = _context()
    run(c, "ls")
    assert _run_mock(c).call_args.kwargs["pty"] is True


def test_run_does_not_use_pty_without_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    c = _context()
    run(c, "ls")
    assert _run_mock(c).call_args.kwargs["pty"] is False


def test_run_uses_pty_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    c = _context({"pty": True})
    run(c, "ls")
    assert _run_mock(c).call_args.kwargs["pty"] is True


def test_run_explicit_pty_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    c = _context()
    run(c, "ls", pty=False)
    assert _run_mock(c).call_args.kwargs["pty"] is False


def test_run_forwards_extra_arguments() -> None:
    c = _context()
    run(c, "ls", warn=True, env={"A": "1"})
    kwargs = _run_mock(c).call_args.kwargs
    assert (kwargs["warn"], kwargs["env"]) == (True, {"A": "1"})


def test_run_returns_the_result_of_the_context() -> None:
    c = _context()
    assert run(c, "ls").command == "ls"


###################################
#     Tests for check_program     #
###################################


def test_check_program_accepts_a_program_on_the_path() -> None:
    assert check_program("ruff check .") is None


def test_check_program_missing_program_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    with pytest.raises(Exit, match=r"'ruff' was not found on the PATH.*'dev' group"):
        check_program("ruff --version")


@pytest.mark.parametrize(
    ("program", "group"),
    [("ruff", "dev"), ("ty", "dev"), ("pre-commit", "dev"), ("mkdocs", "docs"), ("mike", "docs")],
)
def test_check_program_names_the_group_of_a_tool(
    monkeypatch: pytest.MonkeyPatch, program: str, group: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only())
    with pytest.raises(Exit, match=rf"'{group}' group: `uv sync --group {group}`"):
        check_program(f"{program} --version")


def test_check_program_missing_program_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    with pytest.raises(Exit, match=r"'no-such-program' was not found") as excinfo:
        check_program("no-such-program --version")
    assert excinfo.value.code == 127


@pytest.mark.parametrize("command", ["find . -name x", "command -v python"])
def test_check_program_skips_unchecked_programs(
    command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    assert check_program(command) is None


def test_check_program_skips_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    assert check_program("/usr/bin/python -m pytest") is None


def test_check_program_skips_empty_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    assert check_program("") is None


def test_check_program_quoted_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    assert check_program("'/path with space/python' -m pytest") is None


def test_run_missing_program_does_not_run_the_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    c = _context()
    with pytest.raises(Exit, match=r"'ruff' was not found"):
        run(c, "ruff check .")
    assert not _run_mock(c).called


def test_run_without_check_runs_a_missing_program(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", lambda _program: None)
    c = _context()
    run(c, "my-alias --flag", check=False)
    assert _run_mock(c).call_args.args[0] == "my-alias --flag"


def test_run_without_check_does_not_pass_check_to_the_context() -> None:
    c = _context()
    run(c, "ls", check=False)
    assert "check" not in _run_mock(c).call_args.kwargs


@pytest.mark.parametrize(
    "command",
    [
        "FOO=1 ruff check",
        "FOO=1 BAR=2 ruff check",
        "FOO= ruff check",
        "VAR=$(date) ruff check",
        "(ruff check)",
        "{ ruff check; }",
        "$(echo ruff) check",
        "cd docs && ruff check",
        "export FOO=1 && ruff check",
        "test -d docs && ruff check",
        "[ -d docs ] && ruff check",
        "exec ruff check",
        "source env.sh && ruff check",
        ". env.sh && ruff check",
        ": && ruff check",
        "FOO=1",
    ],
)
def test_check_program_accepts_valid_shell_forms(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only("ruff"))
    assert check_program(command) is None


def test_check_program_still_checks_the_program_after_an_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only())
    with pytest.raises(Exit, match=r"^'ruff' was not found on the PATH"):
        check_program("FOO=1 ruff check")


def test_check_program_still_checks_the_program_after_a_builtin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only())
    with pytest.raises(Exit, match=r"^'ruff' was not found on the PATH"):
        check_program("cd docs && ruff check")


###################################
#     Tests for build_command     #
###################################


def test_build_command_uses_default_paths() -> None:
    assert build_command("ruff check", default_paths=["."]) == "ruff check ."


def test_build_command_without_paths_has_only_the_program() -> None:
    assert build_command("ty check") == "ty check"


def test_build_command_adds_args_before_paths() -> None:
    assert build_command("ruff check", args="--select E", default_paths=["."]) == (
        "ruff check --select E ."
    )


def test_build_command_paths_replace_default_paths() -> None:
    assert build_command("ruff check", paths="a.py b.py", default_paths=["."]) == (
        "ruff check a.py b.py"
    )


def test_build_command_quotes_args_with_spaces() -> None:
    assert build_command("pytest", args='-k "a or b"') == "pytest -k 'a or b'"


def test_build_command_quotes_paths_with_spaces() -> None:
    assert build_command("ruff check", paths="'my dir/a.py'") == "ruff check 'my dir/a.py'"


def test_build_command_quotes_shell_metacharacters() -> None:
    assert build_command("ruff check", args="--x ';rm -rf /'") == "ruff check --x ';rm -rf /'"


def test_build_command_does_not_quote_the_program() -> None:
    assert build_command("uv run pip-audit") == "uv run pip-audit"


def test_build_command_unclosed_quote_exits() -> None:
    with pytest.raises(Exit, match=r"Cannot parse the value of --args"):
        build_command("pytest", args="-k 'a")


def test_build_command_unclosed_quote_in_paths_exits() -> None:
    with pytest.raises(Exit, match=r"Cannot parse the value of --paths"):
        build_command("pytest", paths="'a")


def test_build_command_names_the_option_of_the_args_in_the_error() -> None:
    with pytest.raises(Exit, match=r"Cannot parse the value of --other-args"):
        build_command("pytest", args="-k 'a", args_option="--other-args")


def test_build_command_args_option_does_not_change_the_command() -> None:
    assert build_command("pytest", args="-x", args_option="--other-args") == "pytest -x"


################################
#     Tests for split_args     #
################################


def testsplit_args_none() -> None:
    assert split_args(None, "--args") == []


def testsplit_args_empty_string() -> None:
    assert split_args("", "--args") == []


def testsplit_args_keeps_quoted_words_together() -> None:
    assert split_args("-k 'a b' -x", "--args") == ["-k", "a b", "-x"]


def testsplit_args_unclosed_quote_exit_code() -> None:
    with pytest.raises(Exit, match=r"Cannot parse the value of --args") as excinfo:
        split_args("'a", "--args")
    assert excinfo.value.code == 2


###########################################
#     Tests for the hints of programs     #
###########################################


def _only(*available: str) -> Callable[[str], str | None]:
    return lambda program: f"/bin/{program}" if program in available else None


@pytest.mark.parametrize("program", ["uv", "uvx", "git", "shellcheck", "shfmt", "codespell"])
def test_check_program_uses_the_hint_of_the_program(
    monkeypatch: pytest.MonkeyPatch, program: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only())
    with pytest.raises(Exit, match=re.escape(PROGRAM_HINTS[program])):
        check_program(f"{program} --version")


def test_check_program_uv_hint_does_not_suggest_env_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only())
    with pytest.raises(Exit, match=r"^'uv' was not found on the PATH\. Install uv, see https://"):
        check_program("uv sync")


def test_check_program_unknown_program_uses_the_default_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only())
    with pytest.raises(Exit, match=re.escape(DEFAULT_HINT)):
        check_program("no-such-program --version")


def test_check_program_checks_every_stage_of_a_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only("xargs"))
    with pytest.raises(Exit, match=r"'shellcheck' was not found"):
        check_program("find . -name '*.sh' -print0 | xargs -0 -r shellcheck --")


def test_check_program_accepts_a_pipeline_of_available_programs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only("xargs", "shellcheck"))
    assert check_program("find . -name '*.sh' -print0 | xargs -0 -r shellcheck --") is None


def test_check_program_checks_the_second_command_after_and(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only("ruff"))
    with pytest.raises(Exit, match=r"'mike' was not found"):
        check_program("ruff check . && mike list")


def test_check_program_does_not_check_a_word_inside_quotes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only("ruff"))
    assert check_program("ruff check 'a | b'") is None


def test_check_program_xargs_without_command_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.shutil.which", _only("xargs", "echo"))
    assert check_program("echo | xargs -0") is None


def test_check_program_missing_module_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.sys.executable", "/venv/bin/python")
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", lambda _name: None)
    with pytest.raises(
        Exit, match=r"The Python module 'pytest' is not installed for /venv/bin/python"
    ):
        check_program("/venv/bin/python -m pytest tests")


def test_check_program_missing_module_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.sys.executable", "/venv/bin/python")
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", lambda _name: None)
    with pytest.raises(Exit, match=r"module 'pytest' is not installed") as excinfo:
        check_program("/venv/bin/python -m pytest tests")
    assert excinfo.value.code == 127


def test_check_program_missing_module_after_a_pipe_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.sys.executable", "/venv/bin/python")
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", lambda _name: None)
    with pytest.raises(Exit, match=r"The Python module 'coverage' is not installed"):
        check_program("echo && /venv/bin/python -m coverage report")


###################################
#     Tests for _check_module     #
###################################


def test_check_module_accepts_an_installed_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.sys.executable", "/venv/bin/python")
    assert _check_module(["/venv/bin/python", "-m", "pytest"]) is None


def test_check_module_ignores_another_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.sys.executable", "/venv/bin/python")
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", lambda _name: None)
    assert _check_module(["/other/python", "-m", "pytest"]) is None


@pytest.mark.parametrize(
    "words", [["/venv/bin/python"], ["/venv/bin/python", "-m"], ["/venv/bin/python", "-c", "pass"]]
)
def test_check_module_ignores_a_command_that_is_not_a_module_run(
    monkeypatch: pytest.MonkeyPatch, words: list[str]
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.sys.executable", "/venv/bin/python")
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", lambda _name: None)
    assert _check_module(words) is None


def test_check_module_missing_module_uses_the_default_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.sys.executable", "/venv/bin/python")
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", lambda _name: None)
    with pytest.raises(Exit, match=re.escape(DEFAULT_HINT)):
        _check_module(["/venv/bin/python", "-m", "no_such_module_xyz"])


def test_check_module_missing_module_names_its_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.sys.executable", "/venv/bin/python")
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", lambda _name: None)
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


@pytest.mark.parametrize("program", ["uvx", "git", "pre-commit"])
def test_hint_is_not_the_default_for_a_program_env_install_cannot_provide(program: str) -> None:
    assert hint(program) != DEFAULT_HINT


def _missing(*modules: str) -> Callable[[str], object | None]:
    return lambda name: None if name in modules else object()


@pytest.fixture
def _venv_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.sys.executable", "/venv/bin/python")


@pytest.mark.usefixtures("_venv_python")
@pytest.mark.parametrize(
    ("word", "option", "module", "package"),
    [
        ("--xdoctest", "--xdoctest", "xdoctest", "xdoctest"),
        ("--timeout=10", "--timeout", "pytest_timeout", "pytest-timeout"),
        ("--cov=mypkg", "--cov", "pytest_cov", "pytest-cov"),
        ("--benchmark-only", "--benchmark-only", "pytest_benchmark", "pytest-benchmark"),
    ],
)
def test_check_module_missing_pytest_plugin_names_the_package(
    monkeypatch: pytest.MonkeyPatch, word: str, option: str, module: str, package: str
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", _missing(module))
    with pytest.raises(Exit, match=rf"^The option {option} needs .*'{package}'"):
        _check_module(["/venv/bin/python", "-m", "pytest", word, "tests"])


@pytest.mark.usefixtures("_venv_python")
def test_check_module_missing_pytest_plugin_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", _missing("xdoctest"))
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
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", _missing("xdoctest"))
    with pytest.raises(Exit, match=r"xdoctest") as info:
        _check_module(["/venv/bin/python", "-m", "pytest", "--xdoctest"])
    assert info.value.code == 127


@pytest.mark.usefixtures("_venv_python")
def test_check_module_accepts_an_installed_pytest_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", lambda _name: object())
    assert _check_module(["/venv/bin/python", "-m", "pytest", "--xdoctest"]) is None


@pytest.mark.usefixtures("_venv_python")
def test_check_module_missing_pytest_reports_pytest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "invoke_tasklib.runner.importlib.util.find_spec", _missing("pytest", "xdoctest")
    )
    with pytest.raises(Exit, match=r"^The Python module 'pytest' is not installed"):
        _check_module(["/venv/bin/python", "-m", "pytest", "--xdoctest"])


@pytest.mark.usefixtures("_venv_python")
def test_check_module_does_not_check_plugin_options_of_another_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", _missing("xdoctest"))
    assert _check_module(["/venv/bin/python", "-m", "coverage", "--xdoctest"]) is None


###########################################
#     Tests for _check_plugin_options     #
###########################################


def test_check_plugin_options_ignores_other_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", _missing("xdoctest"))
    assert _check_plugin_options(["-x", "-k", "foo", "tests"]) is None


def test_check_plugin_options_no_words_is_ok() -> None:
    assert _check_plugin_options([]) is None


def test_check_plugin_options_stops_at_double_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", _missing("xdoctest"))
    assert _check_plugin_options(["--", "--xdoctest"]) is None


def test_check_plugin_options_reports_the_first_missing_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "invoke_tasklib.runner.importlib.util.find_spec", _missing("xdoctest", "pytest_timeout")
    )
    with pytest.raises(Exit, match=r"^The option --timeout needs .*'pytest-timeout'"):
        _check_plugin_options(["--timeout", "5", "--xdoctest"])


def test_check_plugin_options_looks_the_module_up_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def find_spec(name: str) -> object:
        seen.append(name)
        return object()

    monkeypatch.setattr("invoke_tasklib.runner.importlib.util.find_spec", find_spec)
    _check_plugin_options(["--cov-report", "html"])
    assert seen == ["pytest_cov"]


#############################
#     Tests for _stages     #
#############################


def test_stages_single_command() -> None:
    assert _stages("ruff check .") == [["ruff", "check", "."]]


def test_stages_pipeline() -> None:
    assert _stages("find . -print0 | xargs -0 ls") == [
        ["find", ".", "-print0"],
        ["xargs", "-0", "ls"],
    ]


@pytest.mark.parametrize("separator", ["||", "&&", ";", "&"])
def test_stages_separators(separator: str) -> None:
    assert _stages(f"a x {separator} b y") == [["a", "x"], ["b", "y"]]


def test_stages_keeps_a_separator_inside_quotes() -> None:
    assert _stages("echo 'a | b'") == [["echo", "a | b"]]


def test_stages_empty_command() -> None:
    assert _stages("") == []


def test_stages_drops_empty_commands() -> None:
    assert _stages("; a ; ; b ;") == [["a"], ["b"]]


#################################
#     Tests for _program_of     #
#################################


def test_program_of_a_command() -> None:
    assert _program_of(["ruff", "check"]) == "ruff"


def test_program_of_xargs_is_the_command_it_runs() -> None:
    assert _program_of(["xargs", "-0", "-r", "shellcheck", "--"]) == "shellcheck"


def test_program_of_xargs_without_command_is_none() -> None:
    assert _program_of(["xargs", "-0"]) is None


@pytest.mark.parametrize("words", [["(", "ls", ")"], ["{", "ls"], ["}"], ["$", "(", "ls", ")"]])
def test_program_of_a_subshell_group_or_substitution_is_none(words: list[str]) -> None:
    assert _program_of(words) is None


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
    monkeypatch.setattr(shutil, "which", lambda name: f"/bin/{name}")
    assert find_tool("ruff") == "/bin/ruff"


def test_find_tool_program_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert find_tool("ruff") is None


def test_find_tool_program_is_not_looked_up_as_a_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert find_tool("json") is None


def test_find_tool_module_found_returns_its_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = ModuleSpec("pytest", None, origin="/site/pytest/__init__.py")
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: spec)
    assert find_tool("pytest", module=True) == "/site/pytest/__init__.py"


def test_find_tool_module_without_origin_returns_its_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: ModuleSpec("pytest", None))
    assert find_tool("pytest", module=True) == "pytest"


def test_find_tool_module_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: None)
    assert find_tool("pytest", module=True) is None


def test_find_tool_module_is_not_looked_up_as_a_program(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: None)
    assert find_tool("ruff", module=True) is None
