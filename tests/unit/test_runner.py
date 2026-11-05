from __future__ import annotations

import itertools
import shlex
import shutil
import sys
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit
from invoke.runners import Result

from invoke_tasklib.runner import (
    ARGS_HELP,
    PATHS_HELP,
    TOOL_HELP,
    build_command,
    capture,
    in_ci,
    in_github_actions,
    python_executable,
    run,
    split_args,
)
from invoke_tasklib.tools import tool_path

#######################################
#     Tests for python_executable     #
#######################################


def test_python_executable_returns_running_interpreter() -> None:
    assert python_executable() == sys.executable


def test_python_executable_does_not_quote_a_path_with_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "executable", "/my env/bin/python")
    assert python_executable() == "/my env/bin/python"


def test_run_quotes_a_python_executable_with_a_space(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/my env/bin/python")
    c = _context()
    run(c, [python_executable(), "-m", "pytest"], check=False)
    assert _run_mock(c).call_args.args == ("'/my env/bin/python' -m pytest",)


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


def test_run_quotes_the_words_of_a_list() -> None:
    c = _context()
    run(c, ["ls", "-l", "a b", "*.py", "$HOME", ";"])
    assert _run_mock(c).call_args.args == ("ls -l 'a b' '*.py' '$HOME' ';'",)


def test_run_a_list_of_one_word() -> None:
    c = _context()
    run(c, ["ls"])
    assert _run_mock(c).call_args.args == ("ls",)


def test_run_checks_the_first_word_of_a_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", lambda _program, **_kwargs: None)
    c = _context()
    with pytest.raises(Exit, match=r"'ruff' was not found"):
        run(c, ["ruff", "check", "."])
    assert not _run_mock(c).called


def test_run_does_not_check_a_list_without_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", lambda _program, **_kwargs: None)
    c = _context()
    run(c, ["my-alias", "--flag"], check=False)
    assert _run_mock(c).call_args.args == ("my-alias --flag",)


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
    assert (kwargs["warn"], kwargs["env"]["A"]) == (True, "1")


def test_run_puts_the_interpreter_directory_first_on_the_path() -> None:
    c = _context()
    run(c, "ls")
    assert _run_mock(c).call_args.kwargs["env"]["PATH"] == tool_path()


def test_run_lets_the_caller_set_the_path() -> None:
    c = _context()
    run(c, "ls", env={"PATH": "/custom"})
    assert _run_mock(c).call_args.kwargs["env"] == {"PATH": "/custom"}


def test_run_returns_the_result_of_the_context() -> None:
    c = _context()
    assert run(c, "ls").command == "ls"


def test_run_missing_program_does_not_run_the_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", lambda _program, **_kwargs: None)
    c = _context()
    with pytest.raises(Exit, match=r"'ruff' was not found"):
        run(c, "ruff check .")
    assert not _run_mock(c).called


def test_run_without_check_runs_a_missing_program(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("invoke_tasklib.tools.shutil.which", lambda _program, **_kwargs: None)
    c = _context()
    run(c, "my-alias --flag", check=False)
    assert _run_mock(c).call_args.args[0] == "my-alias --flag"


def test_run_without_check_does_not_pass_check_to_the_context() -> None:
    c = _context()
    run(c, "ls", check=False)
    assert "check" not in _run_mock(c).call_args.kwargs


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


def test_build_command_passes_a_glob_as_it_is() -> None:
    assert build_command("codespell", paths="src/*.py") == "codespell 'src/*.py'"


def test_build_command_passes_a_tilde_as_it_is() -> None:
    assert build_command("codespell", paths="~/x") == "codespell '~/x'"


def test_build_command_does_not_quote_the_program() -> None:
    assert build_command("uv run pip-audit") == "uv run pip-audit"


def test_build_command_of_a_list_returns_a_list() -> None:
    assert build_command(["ruff", "check"], args="--select E", default_paths=["."]) == [
        "ruff",
        "check",
        "--select",
        "E",
        ".",
    ]


def test_build_command_of_a_list_does_not_quote() -> None:
    assert build_command(["codespell"], paths="'my dir/*.py'") == ["codespell", "my dir/*.py"]


def test_build_command_of_a_list_without_options_is_the_words() -> None:
    assert build_command(["ty", "check"]) == ["ty", "check"]


def test_build_command_of_a_list_paths_replace_default_paths() -> None:
    assert build_command(["ruff"], paths="a.py", default_paths=["."]) == ["ruff", "a.py"]


def test_build_command_of_a_list_does_not_change_its_input() -> None:
    words = ["ruff", "check"]
    build_command(words, args="-x", default_paths=["."])
    assert words == ["ruff", "check"]


def test_build_command_of_a_list_unclosed_quote_exits() -> None:
    with pytest.raises(Exit, match=r"Cannot parse the value of --args"):
        build_command(["pytest"], args="-k 'a")


def test_build_command_unclosed_quote_exits() -> None:
    with pytest.raises(Exit, match=r"Cannot parse the value of --args"):
        build_command("pytest", args="-k 'a")


_TRICKY_CHARACTERS = "a *~$'\"\\;&#(é"
_TRICKY_WORDS = ["".join(chars) for chars in itertools.product(_TRICKY_CHARACTERS, repeat=3)][::17]
r"""Words made of the characters that a shell treats specially, every
17th of the 1,331 combinations of three characters."""


@pytest.mark.parametrize("word", _TRICKY_WORDS)
def test_build_command_args_round_trip_through_a_shell_split(word: str) -> None:
    command = build_command("tool", args=shlex.join([word, "x"]))
    assert shlex.split(command) == ["tool", word, "x"]


@pytest.mark.parametrize("word", _TRICKY_WORDS)
def test_build_command_paths_round_trip_through_a_shell_split(word: str) -> None:
    command = build_command("tool", paths=shlex.join([word, "x"]))
    assert shlex.split(command) == ["tool", word, "x"]


@pytest.mark.parametrize("word", _TRICKY_WORDS)
def test_build_command_default_paths_round_trip_through_a_shell_split(word: str) -> None:
    command = build_command("tool", default_paths=[word])
    assert shlex.split(command) == ["tool", word]


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


############################
#     Tests for capture    #
############################


def test_capture_hides_the_output_and_the_command_and_uses_no_pty() -> None:
    c = _context()
    capture(c, "git status")
    kwargs = _run_mock(c).call_args.kwargs
    assert (kwargs["hide"], kwargs["echo"], kwargs["pty"]) == (True, False, False)


def test_capture_does_not_use_a_pty_on_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    c = _context({"pty": True})
    capture(c, "git status")
    assert _run_mock(c).call_args.kwargs["pty"] is False


def test_capture_passes_the_command() -> None:
    c = _context()
    capture(c, "git status")
    assert _run_mock(c).call_args.args == ("git status",)


def test_capture_quotes_the_words_of_a_list() -> None:
    c = _context()
    capture(c, ["git", "log", "--format=%H %s"])
    assert _run_mock(c).call_args.args == ("git log '--format=%H %s'",)


def test_capture_does_not_warn_by_default() -> None:
    c = _context()
    capture(c, "git status")
    assert _run_mock(c).call_args.kwargs["warn"] is False


def test_capture_warns_on_request() -> None:
    c = _context()
    capture(c, "git status", warn=True)
    assert _run_mock(c).call_args.kwargs["warn"] is True


def test_capture_returns_the_result_of_the_context() -> None:
    c = MockContext(config=Config(), run=Result(stdout="out\n"))
    assert capture(c, "git status").stdout == "out\n"


def test_capture_checks_the_program_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name, **_kwargs: None)
    with pytest.raises(Exit, match=r"'nonexistent-tool' was not found"):
        capture(_context(), "nonexistent-tool --version")


def test_capture_can_skip_the_program_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name, **_kwargs: None)
    c = _context()
    capture(c, "nonexistent-tool --version", check=False)
    assert _run_mock(c).call_args.args == ("nonexistent-tool --version",)


def test_capture_does_not_pass_check_to_the_context() -> None:
    c = _context()
    capture(c, "git status")
    assert "check" not in _run_mock(c).call_args.kwargs


###########################
#     Tests for in_ci     #
###########################


@pytest.mark.parametrize("value", ["1", "true", "True", "yes", "anything"])
def test_in_ci_true(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", value)
    assert in_ci() is True


@pytest.mark.parametrize("value", ["", "0", "false", "FALSE", "False", " false "])
def test_in_ci_false(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", value)
    assert in_ci() is False


def test_in_ci_false_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    assert in_ci() is False


def test_in_ci_does_not_depend_on_github_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert in_ci() is False


#######################################
#     Tests for in_github_actions     #
#######################################


def test_in_github_actions_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert in_github_actions() is True


@pytest.mark.parametrize("value", ["", "false", "1", "True", "TRUE", "yes"])
def test_in_github_actions_false_for_another_value(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", value)
    assert in_github_actions() is False


def test_in_github_actions_false_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert in_github_actions() is False


def test_in_github_actions_does_not_depend_on_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("CI", "true")
    assert in_github_actions() is False


###############################
#     Tests for TOOL_HELP     #
###############################


def test_tool_help_is_the_help_of_args_and_paths() -> None:
    assert TOOL_HELP == {"args": ARGS_HELP, "paths": PATHS_HELP}
