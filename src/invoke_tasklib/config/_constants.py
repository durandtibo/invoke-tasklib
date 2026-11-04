r"""Constants of the config: valid values and defaults."""

from __future__ import annotations

import re

EXCLUDED_DIRS: frozenset[str] = frozenset({".venv", ".pytest_cache", ".git", "node_modules"})
r"""Directories that the tasks never walk into (not owned by the
project)."""


PYTHON_VERSION_PATTERN = re.compile(r"\d+\.\d+(\.\d+)?")
r"""Pattern of a valid ``package.python_version`` (``3.10`` or
``3.10.4``)."""


DEFAULT_PYTHON_VERSION = "3.14"
r"""The Python version used when neither ``.python-version`` nor the
``requires-python`` of ``pyproject.toml`` gives one."""


REQUIRES_PYTHON_LOWER_BOUND = re.compile(r"(?:>=|~=|==)\s*(\d+\.\d+)")


COV_REPORTS: frozenset[str] = frozenset(
    {"html", "xml", "json", "lcov", "annotate", "term", "term-missing"}
)
r"""The valid values of ``test.cov_reports`` (the formats of ``--cov-
report`` of pytest-cov)."""


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


TEST_SCOPES: dict[str, str] = {
    "unit_tests": "unit",
    "integration_tests": "integration",
    "functional_tests": "functional",
    "benchmarks": "benchmarks",
}
r"""Default sub-directory of ``paths.tests`` of each test path."""
