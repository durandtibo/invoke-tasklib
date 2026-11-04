r"""Output helpers for user-facing progress messages."""

from __future__ import annotations

import os
import re
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from invoke.context import Context


ASCII_ENV_VAR = "INVOKE_TASKLIB_ASCII"
r"""Environment variable that forces ASCII-only messages when set."""

_ASCII_TAGS: dict[str, str] = {"✅": "[ok]", "❌": "[fail]", "⏭️": "[skip]"}
r"""The symbols that carry a status, and their ASCII tag."""

_EMOJI = re.compile("([\U0001f000-\U0001faff\u2600-\u27bf\u2b00-\u2bff]\ufe0f?|\ufe0f) *")
r"""The emojis, the symbols and the variation selector, with the spaces
that follow them.

The accented letters are not matched.
"""


def _keep_if_encodable(match: re.Match[str], encoding: str) -> str:
    r"""Keep a matched character if the encoding can represent it.

    Args:
        match: A match of ``_EMOJI``: the emoji, with its
            trailing spaces.
        encoding: The encoding of the stream, e.g. ``"ascii"``.

    Returns:
        The matched text, or an empty string if the character cannot
        be encoded.

    Example usage:

    ```pycon
    >>> import re
    >>> from invoke_tasklib.output import _EMOJI, _keep_if_encodable
    >>> match = _EMOJI.search("★ x")
    >>> _keep_if_encodable(match, "cp932")
    '★ '
    >>> _keep_if_encodable(match, "ascii")
    ''

    ```
    """
    try:
        match.group(1).encode(encoding)
    except UnicodeEncodeError:
        return ""
    return match.group(0)


def _to_encoding(text: str, encoding: str) -> str:
    r"""Rewrite a message so that a stream can encode it.

    The status symbols (``✅``, ``❌`` and ``⏭️``) become the tags
    ``[ok]``, ``[fail]`` and ``[skip]``. Any other emoji that the
    encoding cannot represent (the decorative emojis) is removed with
    the space that follows it.
    The other characters, such as the accented letters of a path, are
    kept: the caller replaces those the stream cannot encode.

    Args:
        text: The message.
        encoding: The encoding of the stream, e.g. ``"ascii"``.

    Returns:
        The message, without the emojis ``encoding`` cannot
        represent.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.output import _to_encoding
    >>> _to_encoding("✅ Done", "ascii")
    '[ok] Done'
    >>> _to_encoding("🧹 Cleaning...", "ascii")
    'Cleaning...'

    ```
    """
    for symbol, tag in _ASCII_TAGS.items():
        text = re.sub(f"{symbol} *", f"{tag} ", text)

    return _EMOJI.sub(lambda match: _keep_if_encodable(match, encoding), text)


def say(c: Context, message: str, *, err: bool = False) -> None:
    r"""Write a progress message followed by a newline.

    The message goes to the output stream configured in the invoke
    context (``run.out_stream``), or to ``sys.stdout`` if none is
    configured. With ``err``, it goes to ``run.err_stream`` or to
    ``sys.stderr`` instead, like the message of an ``Exit`` that invoke
    prints, so that a failure and its reason are on the same stream.
    Unlike ``logging``, it needs no logging setup to be
    visible.

    A message never fails a task: if the stream cannot encode a
    character (for example an emoji on an ASCII terminal), the status
    symbols are replaced by the tags ``[ok]``, ``[fail]`` and
    ``[skip]``, the other emojis are removed and any other character
    the stream cannot encode (an accented letter) becomes ``?``. Set
    the environment variable ``INVOKE_TASKLIB_ASCII`` to ``1`` to get
    this ASCII output on any stream.

    Args:
        c: The invoke context.
        message: The message to write.
        err: If True, write to the error stream instead of the output
            stream.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.output import say
    >>> say(Context(config=Config()), "hello")
    hello

    ```
    """
    configured = c.config.run.err_stream if err else c.config.run.out_stream
    stream = configured or (sys.stderr if err else sys.stdout)
    text = f"{message}\n"
    if os.environ.get(ASCII_ENV_VAR, "") not in {"", "0"}:
        text = _to_encoding(text, "ascii").encode("ascii", "replace").decode("ascii")
    try:
        stream.write(text)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
        text = _to_encoding(text, encoding)
        stream.write(text.encode(encoding, "replace").decode(encoding))
    stream.flush()


def _failure_title(start: str) -> str:
    r"""Derive the title of a failed step from its start message.

    Args:
        start: The start message of the step, e.g.
            ``"🎨 Checking code format with ruff..."``.

    Returns:
        The message without the leading symbol and the trailing dots.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.output import _failure_title
    >>> _failure_title("🎨 Checking code format with ruff...")
    'Checking code format with ruff'

    ```
    """
    return re.sub(r"^\W+", "", start).rstrip(".").strip()


@contextmanager
def report_failure(c: Context, title: str) -> Generator[None]:
    r"""Report a failure of a block of a task.

    If the block raises, the failure message
    (``❌ Failed: <title without symbol and dots>``) is written to the
    error stream and the exception is raised again. Nothing is written
    otherwise: use it in a task that writes its own progress messages
    with ``say``; use ``step`` for a block with a start and a done
    message.

    Args:
        c: The invoke context.
        title: What was being done, e.g.
            ``"📦 Installing project dependencies..."``.

    Yields:
        Nothing.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.output import report_failure
    >>> c = Context(config=Config())
    >>> with report_failure(c, "🎨 Checking..."):
    ...     pass
    ...

    ```
    """
    try:
        yield
    except Exception:
        say(c, f"❌ Failed: {_failure_title(title)}", err=True)
        raise


@contextmanager
def step(c: Context, start: str, done: str) -> Generator[None]:
    r"""Report the start and the end of a step of a task.

    The start message is written when the block is entered and the done
    message when it exits normally. If the block raises, a failure
    message (``❌ Failed: <start message without symbol and dots>``) is
    written to the error stream instead and the exception is raised
    again, so that a failed step is visible and not only the output of
    the tool.

    Args:
        c: The invoke context.
        start: The message written when the step starts.
        done: The message written when the step succeeds.

    Yields:
        Nothing.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.output import step
    >>> c = Context(config=Config())
    >>> with step(c, "🎨 Checking...", "✅ Done"):
    ...     pass
    ...
    🎨 Checking...
    ✅ Done

    ```
    """
    say(c, start)
    with report_failure(c, start):
        yield
    say(c, done)
