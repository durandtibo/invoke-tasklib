r"""Invoke tasks for this project, built from ``invoke_tasklib``."""

from __future__ import annotations

from invoke_tasklib import make_ns
from invoke_tasklib.release import build as release_build

__all__ = ["ns"]


ns = make_ns()
ns.add_task(release_build, name="build-package")
