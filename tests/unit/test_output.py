from __future__ import annotations

from io import BytesIO, StringIO, TextIOWrapper
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import Context, MockContext
from invoke.exceptions import Exit, UnexpectedExit
from invoke.runners import Result

from invoke_tasklib import lint
from invoke_tasklib.output import (
    _NON_ASCII,
    ASCII_ENV_VAR,
    _failure_title,
    _keep_if_encodable,
    _to_encoding,
    say,
    step,
)

if TYPE_CHECKING:
    import re

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


def test_say_err_writes_to_stderr_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    say(Context(config=Config()), "oops", err=True)
    assert capsys.readouterr().err == "oops\n"


def test_say_err_does_not_write_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    say(Context(config=Config()), "oops", err=True)
    assert capsys.readouterr().out == ""


def test_say_err_writes_to_the_configured_err_stream() -> None:
    _, err, c = _context_with_err()
    say(c, "oops", err=True)
    assert err.getvalue() == "oops\n"


def test_say_err_does_not_write_to_the_out_stream() -> None:
    out, _, c = _context_with_err()
    say(c, "oops", err=True)
    assert out.getvalue() == ""


def test_say_does_not_write_to_the_err_stream() -> None:
    _, err, c = _context_with_err()
    say(c, "hello")
    assert err.getvalue() == ""


def test_say_err_replaces_characters_the_stream_cannot_encode() -> None:
    raw, stream = _ascii_stream()
    say(Context(config=Config(overrides={"run": {"err_stream": stream}})), "❌ bad", err=True)
    assert raw.getvalue() == b"[fail] bad\n"


def test_say_replaces_characters_the_stream_cannot_encode() -> None:
    raw, stream = _ascii_stream()
    say(Context(config=Config(overrides={"run": {"out_stream": stream}})), "🧹 clean")
    assert raw.getvalue() == b"clean\n"


def test_say_forced_ascii_tags_the_status_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ASCII_ENV_VAR, "1")
    out = StringIO()
    say(Context(config=Config(overrides={"run": {"out_stream": out}})), "✅ Done")
    assert out.getvalue() == "[ok] Done\n"


@pytest.mark.parametrize("value", ["", "0"])
def test_say_keeps_the_symbols_when_ascii_is_off(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(ASCII_ENV_VAR, value)
    out = StringIO()
    say(Context(config=Config(overrides={"run": {"out_stream": out}})), "✅ Done")
    assert out.getvalue() == "✅ Done\n"


def test_say_keeps_the_symbols_when_ascii_is_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ASCII_ENV_VAR, raising=False)
    out = StringIO()
    say(Context(config=Config(overrides={"run": {"out_stream": out}})), "✅ Done")
    assert out.getvalue() == "✅ Done\n"


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
    assert _AsciiOnlyStream.written == ["clean\n"]


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


def _context_with_err() -> tuple[StringIO, StringIO, Context]:
    out, err = StringIO(), StringIO()
    config = Config(overrides={"run": {"out_stream": out, "err_stream": err}})
    return out, err, Context(config=config)


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


def test_step_writes_the_failure_message_to_the_error_stream() -> None:
    _, err, c = _context_with_err()
    with pytest.raises(Exit, match=r"boom"):
        _fail_in_step(c, "🎨 Checking code...", Exit("boom"))
    assert err.getvalue() == "❌ Failed: Checking code\n"


def test_step_writes_no_done_message_when_the_block_fails() -> None:
    out, _, c = _context_with_err()
    with pytest.raises(Exit, match=r"boom"):
        _fail_in_step(c, "🎨 Checking code...", Exit("boom"))
    assert out.getvalue() == "🎨 Checking code...\n"


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
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == (
        "🔍 Checking code linting with ruff...\n",
        "❌ Failed: Checking code linting with ruff\n",
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


##################################
#     Tests for _to_encoding     #
##################################


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("✅ Done", "[ok] Done"),
        ("❌ Failed: x", "[fail] Failed: x"),
        ("⏭️  No tests: skipping", "[skip] No tests: skipping"),
        ("🧹 Cleaning...", "Cleaning..."),
        ("🗑️  Removing build", "Removing build"),
        ("Plain text", "Plain text"),
        ("", ""),
    ],
)
def test_to_encoding_ascii(text: str, expected: str) -> None:
    assert _to_encoding(text, "ascii") == expected


def test_to_encoding_keeps_the_characters_the_encoding_supports() -> None:
    assert _to_encoding("🧹 é ✅ ok", "latin-1") == "é [ok] ok"


def test_to_encoding_handles_several_symbols() -> None:
    assert _to_encoding("✅ a ❌ b", "ascii") == "[ok] a [fail] b"


def test_to_encoding_is_deterministic() -> None:
    assert _to_encoding("✅ a", "ascii") == _to_encoding("✅ a", "ascii")


########################################
#     Tests for _keep_if_encodable     #
########################################


def _match(text: str) -> re.Match[str]:
    match = _NON_ASCII.search(text)
    assert match is not None
    return match


def test_keep_if_encodable_keeps_a_supported_character_and_its_spaces() -> None:
    assert _keep_if_encodable(_match("é  x"), "latin-1") == "é  "


def test_keep_if_encodable_drops_an_unsupported_character_and_its_spaces() -> None:
    assert _keep_if_encodable(_match("é  x"), "ascii") == ""
