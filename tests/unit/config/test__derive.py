from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from invoke_tasklib.config._derive import (
    _default_src,
    _derive_defaults,
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


######################################
#     Tests for _derive_defaults     #
######################################


def _merged(**package: object) -> dict[str, dict[str, object]]:
    return {
        "package": {"name": "my-pkg", "import_name": None, **package},
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


def test_derive_defaults_leaves_the_python_version_to_uv() -> None:
    merged = _merged(python_version=None)
    _derive_defaults(merged)
    assert merged["package"]["python_version"] is None


def test_derive_defaults_keeps_the_python_version_given() -> None:
    merged = _merged(python_version="3.12")
    _derive_defaults(merged)
    assert merged["package"]["python_version"] == "3.12"


def test_derive_defaults_does_not_read_the_python_version_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".python-version").write_text("3.12\n")
    monkeypatch.chdir(tmp_path)
    merged = _merged(python_version=None)
    _derive_defaults(merged)
    assert merged["package"]["python_version"] is None


def test_derive_defaults_rejects_an_invalid_import_name() -> None:
    with pytest.raises(ValueError, match=r"must be a Python module name"):
        _derive_defaults(_merged(import_name="1bad"))
