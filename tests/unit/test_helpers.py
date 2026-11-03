from __future__ import annotations

from invoke.runners import Result

from tests.helpers import commands, make_context

##################################
#     Tests for make_context     #
##################################


def test_make_context_without_config_has_no_tasklib_section() -> None:
    assert "tasklib" not in make_context().config


def test_make_context_sets_the_tasklib_section() -> None:
    assert make_context({"package": {"name": "mypkg"}}).config.tasklib == {
        "package": {"name": "mypkg"}
    }


def test_make_context_records_the_commands_by_default() -> None:
    c = make_context()
    c.run("ls")
    assert commands(c) == ["ls"]


def test_make_context_accepts_a_run_result() -> None:
    c = make_context(run={"ls": Result(stdout="a.py")})
    assert c.run("ls").stdout == "a.py"


##############################
#     Tests for commands     #
##############################


def test_commands_without_calls_is_empty() -> None:
    assert commands(make_context()) == []


def test_commands_keeps_the_order_of_the_calls() -> None:
    c = make_context()
    c.run("b")
    c.run("a")
    assert commands(c) == ["b", "a"]
