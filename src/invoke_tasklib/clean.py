r"""Cleanup tasks."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.tasks import task

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)

DIRS = (
    "build",
    "dist",
    ".pytest_cache",
    ".ruff_cache",
    ".coverage_html",
    "htmlcov",
    ".benchmarks",
    "site",
)
DIR_GLOBS = ("*.egg-info", "**/__pycache__")
FILES = (".coverage", "coverage.xml")


@task
def all(c: Context) -> None:  # noqa: A001, ARG001 (task name/signature required by invoke)
    r"""Remove build artifacts and caches (dist, __pycache__,
    .pytest_cache, .coverage, etc.)."""
    logger.info("🧹 Cleaning build artifacts and caches...")
    for d in DIRS:
        _remove_dir(Path(d))
    for pattern in DIR_GLOBS:
        for p in Path().glob(pattern):
            _remove_dir(p)
    for f in FILES:
        _remove_file(Path(f))
    logger.info("✅ Cleanup complete")


def _remove_dir(path: Path) -> None:
    if path.is_dir():
        logger.info(f"🗑️  Removing {path}")
        shutil.rmtree(path)


def _remove_file(path: Path) -> None:
    if path.is_file():
        logger.info(f"🗑️  Removing {path}")
        path.unlink()
