from __future__ import annotations

from typing import TYPE_CHECKING

from invoke.config import Config
from invoke.context import Context

from invoke_tasklib.config import get_config

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

FULL_CONFIG = {
    "package": {"name": "demo", "import_name": "demo", "python_version": "3.12"},
    "paths": {
        "src": "src/demo",
        "tests": "tests",
        "unit_tests": "tests/unit",
        "integration_tests": "tests/integration",
        "functional_tests": "tests/functional",
        "benchmarks": "tests/benchmarks",
        "docs_config": "docs/mkdocs.yml",
    },
    "groups": {"install": "dev", "update": "dev,docs"},
    "test": {
        "unit_timeout": 10,
        "integration_timeout": 20,
        "functional_timeout": 30,
        "xdoctest": True,
        "timeout": True,
        "cov_fail_under": 90,
        "cov_reports": "html,xml,term",
    },
    "check": {"tasks": "format-python,lint,types,imports,unit", "cov": False},
    "fix": {"tasks": "lint,format-python"},
}


def test_get_config_of_a_full_config(benchmark: BenchmarkFixture) -> None:
    c = Context(config=Config(overrides={"tasklib": FULL_CONFIG}))
    assert benchmark(get_config, c).package.name == "demo"
