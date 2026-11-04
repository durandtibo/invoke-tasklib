r"""Invoke tasks for this project, built from ``invoke_tasklib``."""

from __future__ import annotations

from invoke_tasklib import make_ns
from invoke_tasklib.release import build as release_build

__all__ = ["ns"]


ns = make_ns()
# `inv build-package` is the name that the composite action
# durandtibo/build-pypi-package-action runs (see release-pypi.yaml), so
# it is not a leftover: keep it as long as the action uses it.
ns.add_task(release_build, name="build-package")
