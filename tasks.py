r"""Invoke tasks for this project, built from ``invoke_tasklib``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib import ns
from invoke_tasklib.release import build as release_build

if TYPE_CHECKING:
    from invoke.context import Context

__all__ = ["ns"]


@task(name="build-package")
def build_package(c: Context) -> None:
    r"""Build the package (sdist + wheel).

    Alias for ``release.build``, named to match the ``inv build-
    package`` entry point expected by the ``durandtibo/pypi-release-
    action`` composite actions used in ``.github/workflows/release-
    pypi.yaml``.
    """
    release_build(c)


ns.add_task(build_package)
