r"""Security scanning tasks."""

from __future__ import annotations

import shlex
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.output import say
from invoke_tasklib.runner import run

if TYPE_CHECKING:
    from invoke.context import Context


@task
def audit(c: Context) -> None:
    r"""Audit the locked dependencies for known vulnerabilities.

    The dependencies of ``uv.lock`` are exported to a temporary
    requirements file, which is audited with ``pip-audit`` (run with
    ``uvx``, so it does not have to be a dependency of the project).
    Unlike ``uv run pip-audit``, this does not sync or modify the
    environment, and the result does not depend on what was installed
    last.

    Raises:
        UnexpectedExit: If the lock file is out of date, or if a
            vulnerability is found.
    """
    say(c, "🔒 Auditing locked dependencies for known vulnerabilities...")
    with tempfile.TemporaryDirectory() as tmp:
        requirements = shlex.quote(str(Path(tmp) / "requirements.txt"))
        run(
            c,
            "uv export --locked --no-emit-project --no-hashes --all-groups "
            f"--quiet -o {requirements}",
        )
        run(c, f"uvx pip-audit -r {requirements} --no-deps --disable-pip")
    say(c, "✅ Dependency audit passed")
