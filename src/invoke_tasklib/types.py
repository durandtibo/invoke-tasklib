r"""Type-checking tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.output import say
from invoke_tasklib.runner import PATHS_HELP, build_command, run

if TYPE_CHECKING:
    from invoke.context import Context


@task(
    help={
        "complete": "Also run pyright after ty (slower, more thorough).",
        "args": 'Extra arguments for ty, as one string, e.g. "--python-version 3.12".',
        "paths": PATHS_HELP,
    }
)
def check(
    c: Context, complete: bool = False, args: str | None = None, paths: str | None = None
) -> None:
    r"""Check type hints.

    Two modes are available:

    - fast (default): only ``ty`` is used.
    - complete (``--complete``): ``ty`` and ``pyright`` are both used.

    Args:
        c: The invoke context.
        complete: If ``True``, run ``pyright`` after ``ty``.
        args: Extra arguments passed to ``ty`` (not to ``pyright``).
        paths: The files or directories to check instead of the project
            default, passed to ``ty`` and ``pyright``.
    """
    say(c, "🔬 Checking type hints with ty...")
    run(c, build_command("ty check", args=args, paths=paths))
    if complete:
        say(c, "🔬 Checking type hints with pyright...")
        run(c, build_command("pyright", paths=paths))
    say(c, "✅ Type check passed")
