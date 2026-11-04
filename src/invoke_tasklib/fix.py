r"""Composite task that runs the fixers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib import formatting, lint
from invoke_tasklib._steps import (
    Step,
    missing_tools,
    parse_steps,
    run_steps,
    select_steps,
    step_programs,
    tasks_of,
)
from invoke_tasklib.config import FIX_STEPS, load_config

if TYPE_CHECKING:
    from invoke.context import Context

# The steps of ``fix.all`` (task and programs), by step name.
#
# To add a step, add its name to ``FIX_STEPS`` in
# ``config/_constants.py`` (a test checks that the names agree).
STEPS: dict[str, Step] = {
    "lint": Step(lint.fix_python, programs=("ruff",)),
    "format-python": Step(formatting.fix_python, programs=("ruff",)),
    "format-docstrings": Step(formatting.fix_docstrings, programs=("docformatter",)),
    "shell": Step(formatting.fix_shell, programs=("shfmt",)),
}


@task(
    name="all",
    default=True,
    help={
        "keep_going": "Run every step and report all the failures, instead of stopping.",
        "only": (
            f"Comma-separated steps to run instead of tasklib.fix.tasks ({', '.join(FIX_STEPS)})."
        ),
        "skip": "Comma-separated steps to leave out.",
    },
)
def all_(
    c: Context,
    *,
    keep_going: bool = False,
    only: str | None = None,
    skip: str | None = None,
) -> None:
    r"""Fix the lint and format issues of the project.

    The steps are the ones of ``tasklib.fix.tasks`` (by default
    ``lint``, ``format-python`` and ``format-docstrings``), run in that
    order: the lint fixes come first, so that the formatting has the
    last word on the layout. The other step is ``shell``. The steps
    modify files; ``check.all`` is the read-only counterpart. By
    default the first failure stops the task; with ``keep_going`` every
    step is run and the failed ones are listed at the end.

    Before any step is run, the programs that the selected steps need
    (the programs of ``STEPS``) are looked up and all the missing ones
    are reported at once, with the code 127 and nothing run. With
    ``keep_going``, only the steps that miss a tool are not run: they
    are reported as failed, with the missing tools as the reason.

    Args:
        c: The invoke context.
        keep_going: If True, run all the steps even if one fails.
        only: Comma-separated steps to run instead of the configured
            ones.
        skip: Comma-separated steps to leave out.

    Raises:
        Exit: If a name of ``only`` or ``skip`` is unknown, if a tool
            of the selected steps is missing (code 127), or if
            ``keep_going`` is set and a step failed.
        UnexpectedExit: If a step fails and ``keep_going`` is not set.
    """
    cfg = load_config(c)
    steps = select_steps(
        cfg.fix.tasks,
        parse_steps("--only", only, FIX_STEPS),
        parse_steps("--skip", skip, FIX_STEPS),
    )
    blocked = {
        step: missing
        for step in steps
        if (missing := missing_tools(step_programs(STEPS[step], cfg), ()))
    }
    run_steps(
        c,
        steps,
        tasks_of(STEPS),
        blocked,
        keep_going=keep_going,
        label="fix(es)",
        messages=("🔧 Running all the fixes...", "✅ All fixes applied"),
    )
