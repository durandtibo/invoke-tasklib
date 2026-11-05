r"""Constants of the config: valid values and defaults."""

from __future__ import annotations

import re

EXCLUDED_DIRS: frozenset[str] = frozenset({".venv", ".pytest_cache", ".git", "node_modules"})
r"""Directories that the tasks never walk into (not owned by the
project)."""

PYTHON_VERSION_PATTERN = re.compile(r"\d+\.\d+(\.\d+)?")
r"""Pattern of a valid ``package.python_version`` (``3.10`` or
``3.10.4``)."""

COV_REPORTS: frozenset[str] = frozenset(
    {"html", "xml", "json", "lcov", "annotate", "term", "term-missing"}
)
r"""The valid values of ``test.cov_reports`` (the formats of ``--cov-
report`` of pytest-cov)."""

TYPE_CHECKERS: tuple[str, ...] = ("ty", "pyright", "mypy")
r"""The valid values of ``types.checker``: the type checkers that
``types.check`` can run."""

CHECK_STEPS: tuple[str, ...] = (
    "format-python",
    "format-docstrings",
    "lint",
    "types",
    "imports",
    "unit",
    "doctest",
    "shell",
    "spelling",
    "docs",
    "audit",
)
r"""The steps that ``check.all`` can run (``tasklib.check.tasks``)."""

DEFAULT_CHECK_STEPS: tuple[str, ...] = CHECK_STEPS[:6]
r"""The steps that ``check.all`` runs by default: the first six of
``CHECK_STEPS`` (the formatting, the lint, the types, the imports and
the unit tests)."""

FIX_STEPS: tuple[str, ...] = (
    "lint",
    "format-python",
    "format-docstrings",
    "shell",
)
r"""The steps that ``fix.all`` can run (``tasklib.fix.tasks``).

They are listed in the order that converges: the lint fixes come before
the formatting, which has the last word on the layout.
"""

DEFAULT_FIX_STEPS: tuple[str, ...] = FIX_STEPS[:3]
r"""The steps that ``fix.all`` runs by default: the first three of
``FIX_STEPS`` (everything but ``shell``)."""

TEST_SCOPES: dict[str, str] = {
    "unit_tests": "unit",
    "integration_tests": "integration",
    "functional_tests": "functional",
    "benchmarks": "benchmarks",
}
r"""Default sub-directory of ``paths.tests`` of each test path."""
