r"""Output helpers for user-facing progress messages."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from invoke.context import Context


def say(c: Context, message: str) -> None:
    r"""Write a progress message followed by a newline.

    The message goes to the output stream configured in the invoke
    context (``run.out_stream``), or to ``sys.stdout`` if none is
    configured. Unlike ``logging``, it needs no logging setup to be
    visible.

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
    stream.write(f"{message}\n")
    stream.flush()
