from __future__ import annotations

from io import BytesIO, StringIO, TextIOWrapper
from typing import TYPE_CHECKING, ClassVar

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
    r"""A stream with no ``encoding`` attribute that only accepts ASCII."""

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
