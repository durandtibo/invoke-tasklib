r"""Type-checking tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.output import say
from invoke_tasklib.runner import run

if TYPE_CHECKING:
    from invoke.context import Context


@task(help={"complete": "Also run pyright after ty (slower, more thorough)."})
def check(c: Context, complete: bool = False) -> None:
    r"""Check type hints.

    Two modes are available:

    - fast (default): only ``ty`` is used.
    - complete (``--complete``): ``ty`` and ``pyright`` are both used.

    Args:
        c: The invoke context.
        complete: If ``True``, run ``pyright`` after ``ty``.
    """
    say(c, "🔬 Checking type hints with ty...")
    run(c, "ty check")
    if complete:
        say(c, "🔬 Checking type hints with pyright...")
        run(c, "pyright")
    say(c, "✅ Type check passed")
