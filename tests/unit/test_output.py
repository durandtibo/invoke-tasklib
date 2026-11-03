from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from invoke.config import Config
from invoke.context import Context, MockContext

from invoke_tasklib import lint
from invoke_tasklib.output import say

if TYPE_CHECKING:
    import pytest

#######################
#     Tests for say     #
#######################


def test_say_writes_to_stdout_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    say(Context(config=Config()), "hello")
    assert capsys.readouterr().out == "hello\n"


def test_say_writes_to_configured_out_stream() -> None:
    stream = StringIO()
    say(Context(config=Config(overrides={"run": {"out_stream": stream}})), "hello")
    assert stream.getvalue() == "hello\n"


def test_say_does_not_write_to_stdout_when_out_stream_is_set(
    capsys: pytest.CaptureFixture[str],
) -> None:
    say(Context(config=Config(overrides={"run": {"out_stream": StringIO()}})), "hello")
    assert capsys.readouterr().out == ""


def test_task_progress_messages_are_visible_without_logging_setup(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lint.check_python(MockContext(config=Config(), run=True))
    assert capsys.readouterr().out == (
        "🔍 Checking code linting with ruff...\n✅ Linting check passed\n"
    )
