from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from invoke_tasklib.config._derive import (
    _default_python_version,
    _default_src,
    _derive_defaults,
    _python_version_file,
    _requires_python_lower_bound,
)

if TYPE_CHECKING:
    from pathlib import Path


##################################
#     Tests for _default_src     #
##################################


def test_default_src_prefers_the_src_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src" / "mypkg").mkdir(parents=True)
    (tmp_path / "mypkg").mkdir()
    assert _default_src("mypkg") == "src/mypkg"


def test_default_src_uses_the_flat_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mypkg").mkdir()
    assert _default_src("mypkg") == "mypkg"


def test_default_src_falls_back_to_the_src_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert _default_src("mypkg") == "src/mypkg"


##########################################
#     Tests for _python_version_file     #
##########################################


def test_python_version_file_reads_the_version(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("3.12\n")
    assert _python_version_file(tmp_path) == "3.12"


def test_python_version_file_reads_a_patch_version(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("3.12.1\n")
    assert _python_version_file(tmp_path) == "3.12.1"


def test_python_version_file_skips_comments_and_blank_lines(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("# the version\n\n  3.13  \n3.9\n")
    assert _python_version_file(tmp_path) == "3.13"


def test_python_version_file_is_none_without_the_file(tmp_path: Path) -> None:
    assert _python_version_file(tmp_path) is None


def test_python_version_file_is_none_for_an_empty_file(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("\n# only a comment\n")
    assert _python_version_file(tmp_path) is None


@pytest.mark.parametrize(
    "content", ["cpython-3.12.1-linux-x86_64\n", "pypy3.10\n", "3.12t\n", "3\n"]
)
def test_python_version_file_ignores_other_content(tmp_path: Path, content: str) -> None:
    (tmp_path / ".python-version").write_text(content)
    assert _python_version_file(tmp_path) is None


def test_python_version_file_ignores_a_directory(tmp_path: Path) -> None:
    (tmp_path / ".python-version").mkdir()
    assert _python_version_file(tmp_path) is None


##################################################
#     Tests for _requires_python_lower_bound     #
##################################################


def _pyproject(root: Path, content: str) -> None:
    (root / "pyproject.toml").write_text(content)


@pytest.mark.parametrize(
    ("requires", "expected"),
    [
        (">=3.11", "3.11"),
        (">= 3.9", "3.9"),
        (">=3.10,<4", "3.10"),
        (">=3.11.2", "3.11"),
        ("~=3.12", "3.12"),
        ("==3.13.*", "3.13"),
        ("<4,>=3.8", "3.8"),
    ],
)
def test_requires_python_lower_bound(tmp_path: Path, requires: str, expected: str) -> None:
    _pyproject(tmp_path, f'[project]\nrequires-python = "{requires}"\n')
    assert _requires_python_lower_bound(tmp_path) == expected


@pytest.mark.parametrize("requires", [">3.10", "<4", ">=3", ""])
def test_requires_python_lower_bound_is_none_without_a_lower_bound(
    tmp_path: Path, requires: str
) -> None:
    _pyproject(tmp_path, f'[project]\nrequires-python = "{requires}"\n')
    assert _requires_python_lower_bound(tmp_path) is None


def test_requires_python_lower_bound_is_none_without_the_file(tmp_path: Path) -> None:
    assert _requires_python_lower_bound(tmp_path) is None


def test_requires_python_lower_bound_is_none_without_the_key(tmp_path: Path) -> None:
    _pyproject(tmp_path, '[project]\nname = "demo"\n')
    assert _requires_python_lower_bound(tmp_path) is None


def test_requires_python_lower_bound_is_none_without_a_project_table(tmp_path: Path) -> None:
    _pyproject(tmp_path, "[tool.ruff]\nline-length = 100\n")
    assert _requires_python_lower_bound(tmp_path) is None


def test_requires_python_lower_bound_ignores_a_value_that_is_not_a_string(tmp_path: Path) -> None:
    _pyproject(tmp_path, "[project]\nrequires-python = 3.11\n")
    assert _requires_python_lower_bound(tmp_path) is None


def test_requires_python_lower_bound_ignores_invalid_toml(tmp_path: Path) -> None:
    _pyproject(tmp_path, "[project\n")
    assert _requires_python_lower_bound(tmp_path) is None


#############################################
#     Tests for _default_python_version     #
#############################################


def test_default_python_version_prefers_the_python_version_file(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("3.12\n")
    _pyproject(tmp_path, '[project]\nrequires-python = ">=3.10"\n')
    assert _default_python_version(tmp_path) == "3.12"


def test_default_python_version_uses_requires_python(tmp_path: Path) -> None:
    _pyproject(tmp_path, '[project]\nrequires-python = ">=3.10"\n')
    assert _default_python_version(tmp_path) == "3.10"


def test_default_python_version_uses_requires_python_when_the_file_is_unusable(
    tmp_path: Path,
) -> None:
    (tmp_path / ".python-version").write_text("pypy3.10\n")
    _pyproject(tmp_path, '[project]\nrequires-python = ">=3.10"\n')
    assert _default_python_version(tmp_path) == "3.10"


def test_default_python_version_falls_back_to_the_constant(tmp_path: Path) -> None:
    assert _default_python_version(tmp_path) == "3.14"


######################################
#     Tests for _derive_defaults     #
######################################


def _merged(**package: object) -> dict[str, dict[str, object]]:
    return {
        "package": {"name": "my-pkg", "import_name": None, "python_version": "3.12", **package},
        "paths": {
            "src": None,
            "tests": "tests",
            "unit_tests": None,
            "integration_tests": None,
            "functional_tests": None,
            "benchmarks": None,
        },
    }


def test_derive_defaults_replaces_dashes_in_the_import_name() -> None:
    merged = _merged()
    _derive_defaults(merged)
    assert merged["package"]["import_name"] == "my_pkg"


def test_derive_defaults_keeps_the_import_name_given() -> None:
    merged = _merged(import_name="other")
    _derive_defaults(merged)
    assert merged["package"]["import_name"] == "other"


def test_derive_defaults_derives_the_source_directory() -> None:
    merged = _merged()
    _derive_defaults(merged)
    assert merged["paths"]["src"] == "src/my_pkg"


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("unit_tests", "t/unit"),
        ("integration_tests", "t/integration"),
        ("functional_tests", "t/functional"),
    ],
)
def test_derive_defaults_derives_the_test_paths_from_the_tests_directory(
    key: str, expected: str
) -> None:
    merged = _merged()
    merged["paths"]["tests"] = "t"
    _derive_defaults(merged)
    assert merged["paths"][key] == expected


def test_derive_defaults_derives_the_benchmarks_directory() -> None:
    merged = _merged()
    _derive_defaults(merged)
    assert merged["paths"]["benchmarks"] == "tests/benchmarks"


def test_derive_defaults_keeps_a_test_path_given() -> None:
    merged = _merged()
    merged["paths"]["unit_tests"] = "elsewhere"
    _derive_defaults(merged)
    assert merged["paths"]["unit_tests"] == "elsewhere"


def test_derive_defaults_derives_the_python_version() -> None:
    merged = _merged(python_version=None)
    _derive_defaults(merged)
    assert merged["package"]["python_version"] == "3.14"


def test_derive_defaults_keeps_the_python_version_given() -> None:
    merged = _merged()
    _derive_defaults(merged)
    assert merged["package"]["python_version"] == "3.12"


def test_derive_defaults_rejects_an_invalid_import_name() -> None:
    with pytest.raises(ValueError, match=r"must be a Python module name"):
        _derive_defaults(_merged(import_name="1bad"))
