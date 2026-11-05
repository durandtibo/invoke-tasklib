r"""Type-checking tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.output import say, step
from invoke_tasklib.runner import PATHS_HELP, build_command, run

if TYPE_CHECKING:
    from invoke.context import Context


NAMESPACE = "types"
r"""The name of the namespace of the tasks of this module."""


@task(
    help={
        "complete": "Also run pyright after ty (slower, more thorough).",
        "args": 'Extra arguments for ty, as one string, e.g. "--python-version 3.12".',
        "paths": PATHS_HELP + " Without it, ty checks the project and pyright its own include.",
        "pyright_args": (
            'Extra arguments for pyright (with --complete), e.g. "--pythonversion 3.12".'
        ),
    }
)
def check(
    c: Context,
    *,
    complete: bool = False,
    args: str | None = None,
    paths: str | None = None,
    pyright_args: str | None = None,
) -> None:
    r"""Check type hints.

    Two modes are available:

    - fast (default): only ``ty`` is used.
    - complete (``--complete``): ``ty`` and ``pyright`` are both used.

    Args:
        c: The invoke context.
        complete: If ``True``, run ``pyright`` after ``ty``.
        args: Extra arguments passed to ``ty`` (not to ``pyright``).
        paths: The files or directories to check instead of the
            project default, passed to ``ty`` and ``pyright``. Without
            it, ``ty`` checks the project and ``pyright`` the files of
            its own ``include`` setting, so the two tools can look at
            different files.
        pyright_args: Extra arguments passed to ``pyright`` (not to
            ``ty``). They are only used with ``complete``.
    """
    with step(c, "🔬 Checking type hints with ty...", "✅ Type check passed"):
        run(c, build_command("ty check", args=args, paths=paths))
        if complete:
            say(c, "🔬 Checking type hints with pyright...")
            run(
                c,
                build_command(
                    "pyright", args=pyright_args, paths=paths, args_option="--pyright-args"
                ),
            )
