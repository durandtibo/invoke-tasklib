from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest
from invoke.config import Config
from invoke.context import Context
from invoke.exceptions import Exit

from invoke_tasklib.config import PROJECT_PREFIX_ATTRIBUTE, SCHEMA, get_config, load_config
from invoke_tasklib.config._resolve import _check_project_root
from invoke_tasklib.config._schema import _defaults


def _context(tasklib_config: object = None) -> Context:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return Context(config=Config(overrides=overrides))


def test_get_config_requires_package_name() -> None:
    with pytest.raises(ValueError, match=r"tasklib\.package\.name"):
        get_config(_context())


def test_get_config_defaults() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}}))
    assert asdict(cfg) == {
        "package": {"name": "mypkg", "import_name": "mypkg", "python_version": None},
        "paths": {
            "src": "src/mypkg",
            "tests": "tests",
            "unit_tests": "tests/unit",
            "integration_tests": "tests/integration",
            "functional_tests": "tests/functional",
            "benchmarks": "tests/benchmarks",
            "docs_config": "docs/mkdocs.yml",
        },
        "groups": {"install": ("dev",), "update": ("dev", "docs")},
        "test": {
            "unit_timeout": 10,
            "integration_timeout": 60,
            "functional_timeout": 60,
            "xdoctest": True,
            "timeout": True,
            "cov_fail_under": None,
            "cov_reports": ("html", "xml", "term"),
        },
        "check": {
            "tasks": ("format-python", "format-docstrings", "lint", "types", "imports", "unit"),
            "cov": False,
        },
        "fix": {"tasks": ("lint", "format-python", "format-docstrings")},
    }


def test_get_config_test_overrides() -> None:
    cfg = get_config(
        _context(
            {
                "package": {"name": "mypkg"},
                "test": {
                    "unit_timeout": 5,
                    "integration_timeout": 120,
                    "functional_timeout": 300,
                    "xdoctest": False,
                    "timeout": False,
                    "cov_fail_under": 90,
                    "cov_reports": ["xml"],
                },
            }
        )
    )
    assert asdict(cfg.test) == {
        "unit_timeout": 5,
        "integration_timeout": 120,
        "functional_timeout": 300,
        "xdoctest": False,
        "timeout": False,
        "cov_fail_under": 90,
        "cov_reports": ("xml",),
    }


def test_get_config_test_timeout_must_be_a_boolean() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"timeout": "maybe"}})
    with pytest.raises(ValueError, match=r"'tasklib\.test\.timeout' must be a boolean"):
        get_config(c)


def test_get_config_test_partial_override_keeps_other_defaults() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}, "test": {"unit_timeout": 5}}))
    assert cfg.test.integration_timeout == 60


def test_get_config_test_unknown_key() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"unit_timout": 5}})
    with pytest.raises(
        ValueError,
        match=r"Unknown key 'unit_timout' \(did you mean 'unit_timeout'\?\) in 'tasklib.test'",
    ):
        get_config(c)


def test_get_config_test_invalid_timeout() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"unit_timeout": 0}})
    with pytest.raises(ValueError, match=r"'tasklib.test.unit_timeout' must be an integer >= 1"):
        get_config(c)


def test_get_config_test_invalid_xdoctest() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"xdoctest": "maybe"}})
    with pytest.raises(ValueError, match=r"'tasklib.test.xdoctest' must be a boolean"):
        get_config(c)


@pytest.mark.parametrize("value", [-1, 101, 1000])
def test_get_config_test_invalid_cov_fail_under(value: int) -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_fail_under": value}})
    with pytest.raises(
        ValueError,
        match=r"'tasklib.test.cov_fail_under' must be an integer between 0 and 100",
    ):
        get_config(c)


@pytest.mark.parametrize("value", [0, 100])
def test_get_config_test_cov_fail_under_bounds_are_valid(value: int) -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_fail_under": value}})
    assert get_config(c).test.cov_fail_under == value


def test_get_config_import_name_replaces_hyphens() -> None:
    cfg = get_config(_context({"package": {"name": "my-pkg"}}))
    assert cfg.package.import_name == "my_pkg"


def test_get_config_import_name_override() -> None:
    cfg = get_config(_context({"package": {"name": "my-pkg", "import_name": "other"}}))
    assert cfg.package.import_name == "other"


def test_get_config_src_uses_the_import_name() -> None:
    cfg = get_config(_context({"package": {"name": "my-pkg"}}))
    assert cfg.paths.src == "src/my_pkg"


def test_get_config_explicit_src_wins_over_import_name() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}, "paths": {"src": "lib"}}))
    assert cfg.paths.src == "lib"


def test_get_config_invalid_import_name() -> None:
    c = _context({"package": {"name": "mypkg", "import_name": "my-pkg"}})
    with pytest.raises(ValueError, match=r"'tasklib.package.import_name' must be a Python module"):
        get_config(c)


@pytest.mark.parametrize(
    "key",
    [
        "src",
        "tests",
        "unit_tests",
        "integration_tests",
        "functional_tests",
        "benchmarks",
        "docs_config",
    ],
)
def test_get_config_rejects_an_empty_path(key: str) -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {key: ""}})
    with pytest.raises(ValueError, match=rf"'tasklib\.paths\.{key}' must be a non-empty string"):
        get_config(c)


@pytest.mark.parametrize("value", [5, ["src"], True, 1.5])
def test_get_config_rejects_a_path_that_is_not_a_string(value: object) -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"tests": value}})
    with pytest.raises(ValueError, match=r"'tasklib\.paths\.tests' must be a non-empty string"):
        get_config(c)


@pytest.mark.parametrize("value", [["a"], 5, True])
def test_get_config_rejects_a_package_name_that_is_not_a_string(value: object) -> None:
    c = _context({"package": {"name": value}})
    with pytest.raises(ValueError, match=r"'tasklib\.package\.name' must be a non-empty string"):
        get_config(c)


def test_get_config_rejects_an_unknown_top_level_key() -> None:
    c = _context({"package": {"name": "mypkg"}, "path": {"src": "x"}})
    with pytest.raises(
        ValueError, match=r"Unknown key 'path' \(did you mean 'paths'\?\) in 'tasklib'"
    ):
        get_config(c)


def test_get_config_top_level_error_lists_the_valid_sections() -> None:
    c = _context({"package": {"name": "mypkg"}, "zzz": {}})
    with pytest.raises(ValueError, match=r"Valid keys: check, fix, groups, package, paths, test"):
        get_config(c)


def test_get_config_a_missing_name_is_still_reported_as_unset() -> None:
    with pytest.raises(ValueError, match=r"'tasklib\.package\.name' must be set"):
        get_config(_context({"package": {"name": ""}}))


_OVERRIDES = {
    "package": {"name": "mypkg", "python_version": "3.11"},
    "paths": {"src": "mypkg", "docs_config": "mkdocs.yml"},
}


def test_get_config_overrides_the_python_version() -> None:
    assert get_config(_context(_OVERRIDES)).package.python_version == "3.11"


def test_get_config_overrides_the_src_path() -> None:
    assert get_config(_context(_OVERRIDES)).paths.src == "mypkg"


def test_get_config_check_cov_override() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}, "check": {"cov": True}}))
    assert cfg.check.cov is True


def test_get_config_check_cov_must_be_a_boolean() -> None:
    c = _context({"package": {"name": "mypkg"}, "check": {"cov": "maybe"}})
    with pytest.raises(ValueError, match=r"'tasklib\.check\.cov' must be a boolean"):
        get_config(c)


def test_get_config_overrides_the_docs_config_path() -> None:
    assert get_config(_context(_OVERRIDES)).paths.docs_config == "mkdocs.yml"


def test_get_config_keeps_the_default_of_a_path_not_overridden() -> None:
    assert get_config(_context(_OVERRIDES)).paths.unit_tests == "tests/unit"


def test_get_config_all_paths_overridden() -> None:
    cfg = get_config(
        _context(
            {
                "package": {"name": "mypkg"},
                "paths": {
                    "src": "mypkg",
                    "unit_tests": "tests/u",
                    "integration_tests": "tests/i",
                    "functional_tests": "tests/f",
                    "benchmarks": "tests/b",
                },
            }
        )
    )
    assert asdict(cfg.paths) == {
        "src": "mypkg",
        "tests": "tests",
        "unit_tests": "tests/u",
        "integration_tests": "tests/i",
        "functional_tests": "tests/f",
        "benchmarks": "tests/b",
        "docs_config": "docs/mkdocs.yml",
    }


_GROUPS = {
    "package": {"name": "mypkg"},
    "groups": {"install": "dev,test", "update": "dev,test,docs"},
}


def test_get_config_groups_overrides_install() -> None:
    assert get_config(_context(_GROUPS)).groups.install == ("dev", "test")


def test_get_config_groups_overrides_update() -> None:
    assert get_config(_context(_GROUPS)).groups.update == ("dev", "test", "docs")


########################################
#     Tests for mapping validation     #
########################################


@pytest.mark.parametrize("section", ["package", "paths", "groups", "test"])
def test_get_config_rejects_a_section_that_is_a_string(section: str) -> None:
    c = _context({"package": {"name": "mypkg"}, section: "foo"})
    with pytest.raises(ValueError, match=rf"'tasklib\.{section}' must be a mapping, got 'foo'"):
        get_config(c)


def test_get_config_rejects_a_section_that_is_a_list() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": ["src"]})
    with pytest.raises(ValueError, match=r"'tasklib\.paths' must be a mapping, got \['src'\]"):
        get_config(c)


def test_get_config_rejects_an_empty_section() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": None})
    with pytest.raises(ValueError, match=r"'tasklib\.paths' must be a mapping, got None"):
        get_config(c)


def test_get_config_rejects_a_tasklib_section_that_is_a_string() -> None:
    c = _context("foo")
    with pytest.raises(ValueError, match=r"'tasklib' must be a mapping, got 'foo'"):
        get_config(c)


def test_load_config_exits_on_a_section_that_is_a_string() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": "foo"})
    with pytest.raises(Exit, match=r"'tasklib\.paths' must be a mapping"):
        load_config(c)


###############################################
#     Tests for python_version validation     #
###############################################


@pytest.mark.parametrize("version", [3.1, 3.14, 3, True, ["3.10"]])
def test_get_config_rejects_non_string_python_version(version: object) -> None:
    c = _context({"package": {"name": "mypkg", "python_version": version}})
    with pytest.raises(ValueError, match=r"must be a string like"):
        get_config(c)


def test_get_config_python_version_is_none_by_default() -> None:
    assert get_config(_context({"package": {"name": "mypkg"}})).package.python_version is None


def test_get_config_python_version_ignores_the_python_version_file(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("3.12\n")
    assert get_config(_context({"package": {"name": "mypkg"}})).package.python_version is None


def test_get_config_python_version_ignores_requires_python(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.11"\n')
    assert get_config(_context({"package": {"name": "mypkg"}})).package.python_version is None


def test_get_config_python_version_of_the_config_wins(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("3.12\n")
    cfg = get_config(_context({"package": {"name": "mypkg", "python_version": "3.10"}}))
    assert cfg.package.python_version == "3.10"


def test_get_config_python_version_error_mentions_quoting() -> None:
    c = _context({"package": {"name": "mypkg", "python_version": 3.1}})
    with pytest.raises(ValueError, match=r"Quote the value in invoke\.yaml"):
        get_config(c)


@pytest.mark.parametrize("version", ["3", "3.", "py3.10", "3.10-dev", "3.x", " 3.10", ""])
def test_get_config_rejects_malformed_python_version(version: str) -> None:
    c = _context({"package": {"name": "mypkg", "python_version": version}})
    with pytest.raises(ValueError, match=r"must be a string like"):
        get_config(c)


@pytest.mark.parametrize("version", ["3.10", "3.9", "3.10.4", "3.14"])
def test_get_config_accepts_quoted_python_version(version: str) -> None:
    c = _context({"package": {"name": "mypkg", "python_version": version}})
    assert get_config(c).package.python_version == version


######################################
#     Tests for groups as a list     #
######################################


def test_get_config_groups_install_as_list() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": ["dev", "docs"]}})
    assert get_config(c).groups.install == ("dev", "docs")


def test_get_config_groups_update_as_list() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"update": ["dev", "test"]}})
    assert get_config(c).groups.update == ("dev", "test")


def test_get_config_groups_as_string_is_split() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": "dev,test"}})
    assert asdict(get_config(c).groups) == {"install": ("dev", "test"), "update": ("dev", "docs")}


def test_get_config_groups_as_empty_list_installs_no_group() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": []}})
    assert get_config(c).groups.install == ()


@pytest.mark.parametrize("value", [1, None, ["dev", 1], {"dev": True}])
def test_get_config_rejects_invalid_groups(value: object) -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {"install": value}})
    with pytest.raises(ValueError, match=r"'tasklib\.groups\.install' must be a comma-separated"):
        get_config(c)


##################################
#     Tests for unknown keys     #
##################################


def test_get_config_rejects_unknown_paths_key() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"unit_test": "x"}})
    with pytest.raises(
        ValueError, match=r"Unknown key 'unit_test' \(did you mean 'unit_tests'\?\)"
    ):
        get_config(c)


def test_get_config_rejects_unknown_package_key() -> None:
    c = _context({"package": {"name": "mypkg", "python_versoin": "3.11"}})
    with pytest.raises(
        ValueError, match=r"Unknown key 'python_versoin' \(did you mean 'python_version'"
    ):
        get_config(c)


_MISSPELLED_INSTALL = "instal"  # codespell:ignore instal


def test_get_config_rejects_unknown_groups_key() -> None:
    c = _context({"package": {"name": "mypkg"}, "groups": {_MISSPELLED_INSTALL: "dev"}})
    with pytest.raises(
        ValueError, match=rf"Unknown key '{_MISSPELLED_INSTALL}' \(did you mean 'install'"
    ):
        get_config(c)


def test_get_config_error_names_the_section() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"nope": "x"}})
    with pytest.raises(ValueError, match=r"in 'tasklib\.paths'"):
        get_config(c)


def test_get_config_accepts_every_known_key() -> None:
    c = _context(
        {
            "package": {"name": "mypkg", "python_version": "3.11"},
            "paths": {
                "src": "a",
                "tests": "b",
                "unit_tests": "c",
                "integration_tests": "d",
                "functional_tests": "e",
                "benchmarks": "f",
                "docs_config": "g",
            },
            "groups": {"install": "dev", "update": "dev"},
        }
    )
    assert get_config(c).paths.benchmarks == "f"


#################################
#     Tests for load_config     #
#################################


def test_load_config_returns_the_resolved_config() -> None:
    c = Context(config=Config(overrides={"tasklib": {"package": {"name": "mypkg"}}}))
    assert load_config(c) == get_config(c)


def test_load_config_exits_on_missing_package_name() -> None:
    with pytest.raises(Exit, match=r"'tasklib.package.name' must be set"):
        load_config(Context(config=Config()))


def test_load_config_exit_code_is_2() -> None:
    with pytest.raises(Exit, match=r"'tasklib\.package\.name' must be set") as excinfo:
        load_config(Context(config=Config()))
    assert excinfo.value.code == 2


def test_load_config_exits_on_unknown_key() -> None:
    c = Context(config=Config(overrides={"tasklib": {"paths": {"sr": "x"}}}))
    with pytest.raises(Exit, match=r"Unknown key 'sr'"):
        load_config(c)


def test_get_config_accepts_cov_fail_under_given_as_text() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_fail_under": "90"}})
    assert get_config(c).test.cov_fail_under == 90


def test_get_config_rejects_cov_fail_under_that_is_not_a_number_text() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_fail_under": "high"}})
    with pytest.raises(ValueError, match=r"'tasklib.test.cov_fail_under' must be an integer"):
        get_config(c)


def test_get_config_cov_reports_error_is_reported() -> None:
    c = _context({"package": {"name": "mypkg"}, "test": {"cov_reports": "nope"}})
    with pytest.raises(ValueError, match=r"Unknown coverage report \['nope'\]"):
        get_config(c)


def test_get_config_check_tasks_override() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}, "check": {"tasks": ["lint", "docs"]}}))
    assert cfg.check.tasks == ("lint", "docs")


def test_get_config_check_rejects_an_unknown_key() -> None:
    c = _context({"package": {"name": "mypkg"}, "check": {"task": "lint"}})
    with pytest.raises(ValueError, match=r"Unknown key 'task' \(did you mean 'tasks'\?\)"):
        get_config(c)


def test_get_config_does_not_mutate_the_defaults() -> None:
    before = {section: _defaults(section) for section in SCHEMA}
    get_config(_context({"package": {"name": "mypkg"}, "paths": {"src": "lib"}}))
    assert {section: _defaults(section) for section in SCHEMA} == before


def test_get_config_does_not_mutate_the_user_config() -> None:
    user = {"package": {"name": "my-pkg"}}
    get_config(_context(user))
    assert user == {"package": {"name": "my-pkg"}}


def test_get_config_fix_tasks_override() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}, "fix": {"tasks": "shell, lint"}}))
    assert cfg.fix.tasks == ("shell", "lint")


def test_get_config_rejects_an_unknown_fix_step() -> None:
    c = _context({"package": {"name": "mypkg"}, "fix": {"tasks": "types"}})
    with pytest.raises(ValueError, match=r"Unknown fix step \['types'\]"):
        get_config(c)


def test_get_config_rejects_an_unknown_fix_key() -> None:
    c = _context({"package": {"name": "mypkg"}, "fix": {"task": "lint"}})
    with pytest.raises(ValueError, match=r"Unknown key 'task' \(did you mean 'tasks'"):
        get_config(c)


#####################################
#     Tests for _check_project_root #
#####################################


def _located_context(location: Path | None, name: str = "mypkg") -> Context:
    config = Config(
        overrides={"tasklib": {"package": {"name": name}}},
        project_location=location,
    )
    return Context(config=config)


def test_check_project_root_accepts_the_directory_of_tasks_py(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert _check_project_root(_located_context(tmp_path)) is None


def _context_without_the_attribute(tmp_path: Path) -> Context:
    r"""A context whose config lacks ``_project_prefix``, as if Invoke
    had renamed it."""
    context = _located_context(tmp_path)
    object.__delattr__(context.config, PROJECT_PREFIX_ATTRIBUTE)
    return context


def test_check_project_root_warns_when_invoke_has_no_project_prefix(tmp_path: Path) -> None:
    with pytest.warns(RuntimeWarning, match=r"this version of Invoke has no '_project_prefix'"):
        _check_project_root(_context_without_the_attribute(tmp_path))


def test_check_project_root_is_off_when_invoke_has_no_project_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path.parent)
    with pytest.warns(RuntimeWarning, match=r"Cannot check that inv runs from the project root"):
        assert _check_project_root(_context_without_the_attribute(tmp_path)) is None


def test_check_project_root_does_not_warn_without_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recwarn: pytest.WarningsRecorder
) -> None:
    monkeypatch.chdir(tmp_path)
    _check_project_root(_located_context(None))
    assert len(recwarn) == 0


def test_project_prefix_attribute_exists_on_an_invoke_config() -> None:
    assert hasattr(Config(), PROJECT_PREFIX_ATTRIBUTE)


def test_project_prefix_attribute_holds_the_project_location(tmp_path: Path) -> None:
    assert Path(getattr(Config(project_location=tmp_path), PROJECT_PREFIX_ATTRIBUTE)) == tmp_path


def test_check_project_root_accepts_a_context_without_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert _check_project_root(_located_context(None)) is None


def test_check_project_root_rejects_a_subdirectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sub").mkdir()
    monkeypatch.chdir(tmp_path / "sub")
    with pytest.raises(ValueError, match=r"inv must run from the project root, where tasks\.py is"):
        _check_project_root(_located_context(tmp_path))


def test_check_project_root_names_both_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sub").mkdir()
    monkeypatch.chdir(tmp_path / "sub")
    root = tmp_path.resolve()
    with pytest.raises(
        ValueError, match=rf"{root}.*\(the current directory is {root}/sub\)\. Run 'cd {root}'"
    ):
        _check_project_root(_located_context(tmp_path))


def test_check_project_root_follows_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
    monkeypatch.chdir(tmp_path / "link")
    assert _check_project_root(_located_context(tmp_path / "real")) is None


def test_load_config_exits_from_a_subdirectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sub").mkdir()
    monkeypatch.chdir(tmp_path / "sub")
    with pytest.raises(Exit, match=r"inv must run from the project root"):
        load_config(_located_context(tmp_path))


def test_load_config_exit_code_is_2_from_a_subdirectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sub").mkdir()
    monkeypatch.chdir(tmp_path / "sub")
    with pytest.raises(Exit) as info:
        load_config(_located_context(tmp_path))
    assert info.value.code == 2


def test_get_config_ignores_the_none_registered_for_a_boolean() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}, "test": {"xdoctest": None}}))
    assert cfg.test.xdoctest is True


def test_get_config_ignores_the_none_registered_for_an_integer() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}, "test": {"unit_timeout": None}}))
    assert cfg.test.unit_timeout == 10


def test_get_config_parses_a_boolean_given_as_text() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}, "test": {"xdoctest": "false"}}))
    assert cfg.test.xdoctest is False


def test_get_config_parses_an_integer_given_as_text() -> None:
    cfg = get_config(_context({"package": {"name": "mypkg"}, "test": {"unit_timeout": "30"}}))
    assert cfg.test.unit_timeout == 30
