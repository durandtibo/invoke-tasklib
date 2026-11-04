r"""Security scanning tasks."""

from __future__ import annotations

import shlex
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.output import step
from invoke_tasklib.runner import ARGS_HELP, build_command, run

if TYPE_CHECKING:
    from invoke.context import Context

# The version range of ``pip-audit`` that ``security.audit`` runs.
# ``uvx`` installs the latest release in this range, so a new major
# version is never run without a change of this constant.
PIP_AUDIT_REQUIREMENT = "pip-audit>=2.10,<3"


@task(help={"args": ARGS_HELP})
def audit(c: Context, *, args: str | None = None) -> None:
    r"""Audit the locked dependencies for known vulnerabilities.

    The dependencies of ``uv.lock`` are exported to a temporary
    requirements file, which is audited with ``pip-audit`` (run with
    ``uvx``, so it does not have to be a dependency of the project, in
    the range ``PIP_AUDIT_REQUIREMENT``).
    Unlike ``uv run pip-audit``, this does not sync or modify the
    environment, and the result does not depend on what was installed
    last.

    Args:
        c: The invoke context.
        args: Extra arguments passed to pip-audit, e.g.
            ``"--ignore-vuln PYSEC-2024-1"``.

    Raises:
        UnexpectedExit: If the lock file is out of date, or if a
            vulnerability is found.
    """
    with (
        step(
            c,
            "🔒 Auditing locked dependencies for known vulnerabilities...",
            "✅ Dependency audit passed",
        ),
        tempfile.TemporaryDirectory() as tmp,
    ):
        requirements = shlex.quote(str(Path(tmp) / "requirements.txt"))
        run(
            c,
            "uv export --locked --no-emit-project --no-hashes --all-groups "
            f"--quiet -o {requirements}",
        )
        tool = shlex.quote(PIP_AUDIT_REQUIREMENT)
        cmd = f"uvx --from {tool} pip-audit -r {requirements} --no-deps --disable-pip"
        run(c, build_command(cmd, args=args))
