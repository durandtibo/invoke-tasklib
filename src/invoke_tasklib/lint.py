r"""Lint tasks (``lint.*``).

The Python code is linted with ruff, the text with codespell, and
``lint.pre-commit`` runs the pre-commit hooks of the project.

Naming convention: ``check_<target>`` tasks are read-only;
``fix_<target>`` tasks modify files in place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.output import step
from invoke_tasklib.runner import ARGS_HELP, TOOL_HELP, build_command, in_github_actions, run

if TYPE_CHECKING:
    from invoke.context import Context


# The name of the namespace of the tasks of this module.
NAMESPACE = "lint"


@task(
    help={
        "output_format": (
            "Ruff output format. Defaults to 'github' when GITHUB_ACTIONS is 'true', "
            "ruff's own default otherwise."
        ),
        **TOOL_HELP,
    }
)
def check_python(
    c: Context,
    *,
    output_format: str | None = None,
    args: str | None = None,
    paths: str | None = None,
) -> None:
    r"""Check code linting with ruff.

    Args:
        c: The invoke context.
        output_format: The ``--output-format`` passed to ruff. If not
            set, ``github`` is used when running in GitHub Actions
            (``GITHUB_ACTIONS=true``), where it creates annotations, and
            ruff's default format is used otherwise.
        args: Extra arguments passed to ruff, e.g. ``"--select E"``.
        paths: The files or directories to check instead of the whole
            project (``.``).
    """
    if output_format is None and in_github_actions():
        output_format = "github"
    with step(c, "🔍 Checking code linting with ruff...", "✅ Linting check passed"):
        option = [f"--output-format={output_format}"] if output_format else []
        run(
            c,
            build_command(["ruff", "check", *option], args=args, paths=paths, default_paths=["."]),
        )


@task(help=TOOL_HELP)
def fix_python(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Fix auto-fixable linting issues in place with ruff.

    Args:
        c: The invoke context.
        args: Extra arguments passed to ruff, e.g. ``"--select I"``.
        paths: The files or directories to fix instead of the whole
            project (``.``).

    Note:
        This modifies files in place. Ensure your work is committed
        before running this task.
    """
    with step(c, "🔧 Fixing linting issues with ruff...", "✅ Linting fix complete"):
        run(
            c,
            build_command(["ruff", "check", "--fix"], args=args, paths=paths, default_paths=["."]),
        )


@task(help=TOOL_HELP)
def check_spelling(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Check the spelling with codespell.

    The configuration of codespell is read from the project
    (``pyproject.toml``). The files are not modified.

    Args:
        c: The invoke context.
        args: Extra arguments passed to codespell.
        paths: The files or directories to check instead of the whole
            project (``.``).
    """
    with step(c, "🔤 Checking spelling with codespell...", "✅ Spelling check passed"):
        run(c, build_command(["codespell"], args=args, paths=paths, default_paths=["."]))


@task(help={"args": ARGS_HELP})
def pre_commit(c: Context, *, args: str | None = None) -> None:
    r"""Run all the pre-commit hooks on all the files.

    Args:
        c: The invoke context.
        args: Extra arguments passed to ``pre-commit run``, e.g.
            ``"ruff-format"`` to run one hook.

    Note:
        The hooks may modify files in place.
    """
    with step(c, "🪝 Running the pre-commit hooks...", "✅ Pre-commit hooks passed"):
        run(c, build_command(["pre-commit", "run", "--all-files"], args=args))
