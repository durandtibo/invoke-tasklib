from __future__ import annotations

from io import BytesIO, StringIO, TextIOWrapper
from typing import ClassVar
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import Context, MockContext
from invoke.exceptions import Exit, UnexpectedExit
from invoke.runners import Result

from invoke_tasklib import lint
from invoke_tasklib.output import _failure_title, say, step

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


def _ascii_stream() -> tuple[BytesIO, TextIOWrapper]:
    raw = BytesIO()
    return raw, TextIOWrapper(raw, encoding="ascii", write_through=True)


def test_say_replaces_characters_the_stream_cannot_encode() -> None:
    raw, stream = _ascii_stream()
    say(Context(config=Config(overrides={"run": {"out_stream": stream}})), "🧹 clean")
    assert raw.getvalue() == b"? clean\n"


def test_say_keeps_encodable_characters_on_ascii_stream() -> None:
    raw, stream = _ascii_stream()
    say(Context(config=Config(overrides={"run": {"out_stream": stream}})), "hello")
    assert raw.getvalue() == b"hello\n"


class _AsciiOnlyStream:
    r"""A stream without ``encoding`` that only accepts ASCII."""

    written: ClassVar[list[str]] = []

    def write(self, text: str) -> None:
        if not text.isascii():
            codec, msg = "ascii", "not ascii"
            raise UnicodeEncodeError(codec, text, 0, 1, msg)
        self.written.append(text)

    def flush(self) -> None:
        pass


def test_say_replaces_characters_on_stream_without_encoding() -> None:
    _AsciiOnlyStream.written.clear()
    say(Context(config=Config(overrides={"run": {"out_stream": _AsciiOnlyStream()}})), "🧹 clean")
    assert _AsciiOnlyStream.written == ["? clean\n"]


def test_task_progress_messages_are_visible_without_logging_setup(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lint.check_python(MockContext(config=Config(), run=True))
    assert capsys.readouterr().out == (
        "🔍 Checking code linting with ruff...\n✅ Linting check passed\n"
    )


#########################
#     Tests for step    #
#########################


def _context() -> tuple[StringIO, Context]:
    stream = StringIO()
    return stream, Context(config=Config(overrides={"run": {"out_stream": stream}}))


def test_step_writes_the_start_then_the_done_message() -> None:
    stream, c = _context()
    with step(c, "🎨 Checking...", "✅ Done"):
        pass
    assert stream.getvalue() == "🎨 Checking...\n✅ Done\n"


def test_step_writes_the_start_message_before_the_body() -> None:
    stream, c = _context()
    with step(c, "start", "done"):
        seen = stream.getvalue()
    assert seen == "start\n"


def _fail_in_step(c: Context, start: str, error: BaseException) -> None:
    with step(c, start, "done"):
        raise error


def test_step_writes_a_failure_message_instead_of_the_done_message() -> None:
    stream, c = _context()
    with pytest.raises(Exit, match=r"boom"):
        _fail_in_step(c, "🎨 Checking code...", Exit("boom"))
    assert stream.getvalue() == "🎨 Checking code...\n❌ Failed: Checking code\n"


def test_step_raises_the_same_exception() -> None:
    _, c = _context()
    error = UnexpectedExit(Result(exited=2, command="ruff"))
    with pytest.raises(UnexpectedExit) as info:
        _fail_in_step(c, "start", error)
    assert info.value is error


def test_step_does_not_report_a_keyboard_interrupt_as_a_failure() -> None:
    stream, c = _context()
    with pytest.raises(KeyboardInterrupt, match=r"stop"):
        _fail_in_step(c, "start", KeyboardInterrupt("stop"))
    assert stream.getvalue() == "start\n"


def test_step_can_be_nested() -> None:
    stream, c = _context()
    with step(c, "outer", "outer done"), step(c, "inner", "inner done"):
        pass
    assert stream.getvalue() == "outer\ninner\ninner done\nouter done\n"


def test_task_failure_is_visible_after_the_start_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    c = MockContext(config=Config(), run=True)
    c.run = Mock(side_effect=UnexpectedExit(Result(exited=1)))
    with pytest.raises(UnexpectedExit):
        lint.check_python(c)
    assert capsys.readouterr().out == (
        "🔍 Checking code linting with ruff...\n❌ Failed: Checking code linting with ruff\n"
    )


################################
#     Tests for _failure_title #
################################


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        ("🎨 Checking code format with ruff...", "Checking code format with ruff"),
        ("🗑️  Removing build", "Removing build"),
        ("Plain text...", "Plain text"),
        ("🔍 Verifying é.whl...", "Verifying é.whl"),
        ("...", ""),
        ("", ""),
    ],
)
def test_failure_title(start: str, expected: str) -> None:
    assert _failure_title(start) == expected
