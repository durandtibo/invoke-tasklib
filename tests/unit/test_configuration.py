from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from invoke.config import Config
from invoke.context import Context
from invoke.exceptions import Exit

from invoke_tasklib import configuration
from invoke_tasklib.config import default_config, get_config

if TYPE_CHECKING:
    from collections.abc import Mapping

_BASE_DEFAULTS = {**Config.global_defaults(), "tasklib": default_config()}
_MINIMAL = {"package": {"name": "demo", "python_version": "3.12"}}


def _context(tasklib: Mapping[str, object] | None = None) -> Context:
    r"""A context whose config has the defaults of the library and the
    given ``tasklib`` section as overrides."""
    overrides = {} if tasklib is None else {"tasklib": tasklib}
    return Context(config=Config(defaults=_BASE_DEFAULTS, overrides=overrides))


###################################
#     Tests for _format_value     #
###################################


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "null"),
        (True, "true"),
        (False, "false"),
        (10, "10"),
        ("src/pkg", "src/pkg"),
        ("tests", "tests"),
        ("docs/mkdocs.yml", "docs/mkdocs.yml"),
        ("3.12", '"3.12"'),
        ("true", '"true"'),
        ("null", '"null"'),
        ("my pkg", '"my pkg"'),
        ("a: b", '"a: b"'),
        ("", '""'),
        (("dev", "docs"), "[dev, docs]"),
        (("dev",), "[dev]"),
        ((), "[]"),
        (["a"], "[a]"),
    ],
)
def test_format_value(value: object, expected: str) -> None:
    assert configuration._format_value(value) == expected


#############################
#     Tests for _origin     #
#############################


def test_origin_of_a_default_value() -> None:
    config = Config(defaults=_BASE_DEFAULTS)
    assert configuration._origin(config, "paths", "tests", "tests") == "default"


def test_origin_of_a_derived_value() -> None:
    config = Config(defaults=_BASE_DEFAULTS)
    assert configuration._origin(config, "paths", "src", "src/demo") == "derived"


def test_origin_of_an_unset_value_is_default() -> None:
    config = Config(defaults=_BASE_DEFAULTS)
    assert configuration._origin(config, "test", "cov_fail_under", None) == "default"


def test_origin_of_an_override() -> None:
    config = Config(overrides={"tasklib": {"paths": {"src": "lib"}}})
    assert configuration._origin(config, "paths", "src", "lib") == "override"


def test_origin_names_the_environment_variable() -> None:
    config = Config()
    config._set(_env={"tasklib": {"test": {"unit_timeout": 5}}})
    assert (
        configuration._origin(config, "test", "unit_timeout", 5)
        == "environment variable INVOKE_TASKLIB_TEST_UNIT_TIMEOUT"
    )


def test_origin_of_the_project_file() -> None:
    config = Config()
    config._set(_project={"tasklib": {"paths": {"src": "lib"}}})
    assert configuration._origin(config, "paths", "src", "lib") == "project file"


def test_origin_prefers_the_environment_to_the_project_file() -> None:
    config = Config()
    config._set(
        _project={"tasklib": {"paths": {"src": "a"}}}, _env={"tasklib": {"paths": {"src": "b"}}}
    )
    assert configuration._origin(config, "paths", "src", "b").startswith("environment variable")


def test_origin_prefers_an_override_to_the_environment() -> None:
    config = Config(overrides={"tasklib": {"paths": {"src": "a"}}})
    config._set(_env={"tasklib": {"paths": {"src": "b"}}})
    assert configuration._origin(config, "paths", "src", "a") == "override"


def test_origin_of_a_value_given_as_false_is_not_derived() -> None:
    config = Config(overrides={"tasklib": {"test": {"xdoctest": False}}})
    assert configuration._origin(config, "test", "xdoctest", False) == "override"


#############################
#     Tests for _render     #
#############################


def _lines(tasklib: Mapping[str, object]) -> list[str]:
    config = Config(defaults=_BASE_DEFAULTS, overrides={"tasklib": tasklib})
    return configuration._render(get_config(Context(config=config)), config)


def test_render_the_whole_config() -> None:
    assert _lines(_MINIMAL) == [
        "tasklib:",
        "  package:",
        "    name: demo  # override",
        "    import_name: demo  # derived",
        '    python_version: "3.12"  # override',
        "  paths:",
        "    src: src/demo  # derived",
        "    tests: tests  # default",
        "    unit_tests: tests/unit  # derived",
        "    integration_tests: tests/integration  # derived",
        "    functional_tests: tests/functional  # derived",
        "    benchmarks: tests/benchmarks  # derived",
        "    docs_config: docs/mkdocs.yml  # default",
        "  groups:",
        "    install: [dev]  # default",
        "    update: [dev, docs]  # default",
        "  test:",
        "    unit_timeout: 10  # default",
        "    integration_timeout: 60  # default",
        "    functional_timeout: 60  # default",
        "    xdoctest: true  # default",
        "    cov_fail_under: null  # default",
        "    cov_reports: [html, xml, term]  # default",
        "  check:",
        "    tasks: [format-python, format-docstrings, lint, types, imports, unit]  # default",
        "    cov: false  # default",
        "  fix:",
        "    tasks: [lint, format-python, format-docstrings]  # default",
    ]


def test_render_shows_a_value_of_the_user() -> None:
    lines = _lines({**_MINIMAL, "paths": {"src": "lib"}})
    assert "    src: lib  # override" in lines


def test_render_derives_the_test_paths_from_the_tests_directory() -> None:
    lines = _lines({**_MINIMAL, "paths": {"tests": "t"}})
    assert "    unit_tests: t/unit  # derived" in lines


def test_render_does_not_change_the_config() -> None:
    config = Config(defaults=_BASE_DEFAULTS, overrides={"tasklib": _MINIMAL})
    before = config.tasklib.paths.src
    configuration._render(get_config(Context(config=config)), config)
    assert config.tasklib.paths.src == before


##########################
#     Tests for show     #
##########################


def test_show_prints_the_lines(capsys: pytest.CaptureFixture[str]) -> None:
    configuration.show(_context(_MINIMAL))
    assert capsys.readouterr().out.splitlines()[:3] == [
        "tasklib:",
        "  package:",
        "    name: demo  # override",
    ]


def test_show_prints_nothing_else(capsys: pytest.CaptureFixture[str]) -> None:
    configuration.show(_context(_MINIMAL))
    assert capsys.readouterr().out.splitlines()[-1].startswith("    tasks: [lint, ")


def test_show_exits_on_an_invalid_config() -> None:
    with pytest.raises(Exit, match=r"tasklib\.package\.name"):
        configuration.show(_context())


def test_show_is_the_one_task_of_the_module() -> None:
    assert configuration.show.__name__ == "show"
