r"""Constants of the config: valid values and defaults."""

from __future__ import annotations

import re

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

TEST_SCOPES: dict[str, str] = {
    "unit_tests": "unit",
    "integration_tests": "integration",
    "functional_tests": "functional",
    "benchmarks": "benchmarks",
}
r"""Default sub-directory of ``paths.tests`` of each test path."""
