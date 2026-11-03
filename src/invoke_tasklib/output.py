r"""Output helpers for user-facing progress messages."""

from __future__ import annotations

import re
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from invoke.context import Context


def say(c: Context, message: str) -> None:
    r"""Write a progress message followed by a newline.

    The message goes to the output stream configured in the invoke
    context (``run.out_stream``), or to ``sys.stdout`` if none is
    configured. Unlike ``logging``, it needs no logging setup to be
    visible.

    A message never fails a task: if the stream cannot encode a
    character (for example an emoji on an ASCII terminal), the
    character is replaced by ``?``.

    Args:
        c: The invoke context.
        message: The message to write.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.output import say
    >>> say(Context(config=Config()), "hello")
    hello

    ```
    """
    stream = c.config.run.out_stream or sys.stdout
    text = f"{message}\n"
    try:
        stream.write(text)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
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
def step(c: Context, start: str, done: str) -> Generator[None]:
    r"""Report the start and the end of a step of a task.

    The start message is written when the block is entered and the done
    message when it exits normally. If the block raises, a failure
    message (``❌ Failed: <start message without symbol and dots>``) is
    written instead and the exception is raised again, so that a failed
    step is visible and not only the output of the tool.

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
    try:
        yield
    except Exception:
        say(c, f"❌ Failed: {_failure_title(start)}")
        raise
    say(c, done)
