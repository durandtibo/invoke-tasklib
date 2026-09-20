from __future__ import annotations

import pytest
from invoke.config import Config
from invoke.context import Context

from invoke_tasklib.config import get_config


def _context(tasklib_config: dict | None = None) -> Context:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return Context(config=Config(overrides=overrides))


def test_get_config_requires_package_name() -> None:
    with pytest.raises(ValueError, match="tasklib.package.name"):
        get_config(_context())


def test_get_config_defaults() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}}))
    assert cfg == {
        "package": {"name": "mypkg", "python_version": "3.12"},
        "paths": {
            "src": "src/mypkg",
            "tests": "tests",
            "unit_tests": "tests/unit",
            "integration_tests": "tests/integration",
            "benchmarks": "tests/benchmarks",
            "docs_config": "docs/mkdocs.yml",
        },
    }


def test_get_config_overrides() -> None:
    cfg = get_config(
        _context(
            {
                "package": {"name": "mypkg", "python_version": "3.11"},
                "paths": {"src": "mypkg", "docs_config": "mkdocs.yml"},
            }
        )
    )
    assert cfg["package"]["python_version"] == "3.11"
    assert cfg["paths"]["src"] == "mypkg"
    assert cfg["paths"]["docs_config"] == "mkdocs.yml"
    assert cfg["paths"]["unit_tests"] == "tests/unit"
