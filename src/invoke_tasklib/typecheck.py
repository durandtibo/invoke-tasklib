r"""Type-checking tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import load_config
from invoke_tasklib.output import say, step
from invoke_tasklib.runner import PATHS_HELP, build_command, run

if TYPE_CHECKING:
    from invoke.context import Context


NAMESPACE = "types"
r"""The name of the namespace of the tasks of this module."""


COMMANDS: dict[str, str] = {"ty": "ty check", "pyright": "pyright", "mypy": "mypy"}
r"""The command of each type checker of ``types.checker``."""


@task(
    help={
        "complete": "Also run pyright after the checker (slower, more thorough).",
        "args": 'Extra arguments for the checker, as one string, e.g. "--python-version 3.12".',
        "paths": PATHS_HELP + " Without it, the checker checks the project.",
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

    The checker is ``tasklib.types.checker`` (``ty`` by default, or
    ``pyright`` or ``mypy``). Two modes are available:

    - fast (default): only the checker is used.
    - complete (``--complete``): ``pyright`` is also run after the
      checker, unless the checker is ``pyright``.

    Args:
        c: The invoke context.
        complete: If ``True``, run ``pyright`` after the checker.
        args: Extra arguments passed to the checker (not to the extra
            ``pyright`` run).
        paths: The files or directories to check instead of the
            project default, passed to the checker and ``pyright``.
        pyright_args: Extra arguments passed to the extra ``pyright``
            run. They are only used with ``complete``.
    """
    checker = load_config(c).types.checker
    with step(c, f"🔬 Checking type hints with {checker}...", "✅ Type check passed"):
        run(c, build_command(COMMANDS[checker], args=args, paths=paths))
        if complete and checker != "pyright":
            say(c, "🔬 Checking type hints with pyright...")
            run(
                c,
                build_command(
                    "pyright", args=pyright_args, paths=paths, args_option="--pyright-args"
                ),
            )
