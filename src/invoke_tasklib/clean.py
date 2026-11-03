r"""Cleanup tasks."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from invoke_tasklib.output import say

if TYPE_CHECKING:
    from invoke.context import Context

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


def all(c: Context) -> None:  # noqa: A001 (task name required by invoke)
    r"""Remove build artifacts and caches (dist, __pycache__,
    .pytest_cache, .coverage, etc.)."""
    say(c, "🧹 Cleaning build artifacts and caches...")
    for d in DIRS:
        _remove_dir(c, Path(d))
    for pattern in DIR_GLOBS:
        for p in Path().glob(pattern):
            _remove_dir(c, p)
    for f in FILES:
        _remove_file(c, Path(f))
    say(c, "✅ Cleanup complete")


def pycache(c: Context) -> None:
    r"""Remove all ``__pycache__`` directories."""
    say(c, "🧹 Cleaning __pycache__ directories...")
    for p in Path().glob("**/__pycache__"):
        _remove_dir(c, p)
    say(c, "✅ Cleanup complete")


def _remove_dir(c: Context, path: Path) -> None:
    if path.is_dir():
        say(c, f"🗑️  Removing {path}")
        shutil.rmtree(path)


def _remove_file(c: Context, path: Path) -> None:
    if path.is_file():
        say(c, f"🗑️  Removing {path}")
        path.unlink()
