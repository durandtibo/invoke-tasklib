from __future__ import annotations

import importlib
import runpy
import sys
from typing import TYPE_CHECKING

import pytest

from invoke_tasklib._discover import _walk, discover_modules, find_spec, main

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "discoverpkg"
    (root / "sub" / "deep").mkdir(parents=True)
    for rel in (
        "__init__.py",
        "a.py",
        "__main__.py",
        "sub/__init__.py",
        "sub/b.py",
        "sub/deep/__init__.py",
    ):
        (root / rel).write_text("raise RuntimeError('imported')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    return root


######################################
#     Tests for discover_modules     #
######################################


def test_discover_modules_lists_package_and_all_modules(pkg: Path) -> None:
    assert discover_modules(pkg.name) == [
        "discoverpkg",
        "discoverpkg.a",
        "discoverpkg.sub",
        "discoverpkg.sub.b",
        "discoverpkg.sub.deep",
    ]


def test_discover_modules_does_not_import_anything(pkg: Path) -> None:
    discover_modules(pkg.name)
    assert pkg.name not in sys.modules


def test_discover_modules_excludes_main(pkg: Path) -> None:
    assert "discoverpkg.__main__" not in discover_modules(pkg.name)


def test_discover_modules_single_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "discoversingle.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    assert discover_modules("discoversingle") == ["discoversingle"]


def test_discover_modules_unknown_package() -> None:
    with pytest.raises(ModuleNotFoundError, match=r"No module named 'no_such_pkg_xyz'"):
        discover_modules("no_such_pkg_xyz")


@pytest.fixture
def namespace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r"""A package ``outerpkg`` whose code fails if it is imported,
    with the subpackage ``outerpkg.inner``."""
    root = tmp_path / "outerpkg"
    (root / "inner").mkdir(parents=True)
    (root / "__init__.py").write_text("raise RuntimeError('imported')\n")
    (root / "inner" / "__init__.py").write_text("")
    (root / "inner" / "mod.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    return root


@pytest.mark.usefixtures("namespace")
def test_discover_modules_of_a_dotted_name() -> None:
    assert discover_modules("outerpkg.inner") == ["outerpkg.inner", "outerpkg.inner.mod"]


@pytest.mark.usefixtures("namespace")
def test_discover_modules_of_a_dotted_name_does_not_import_the_parent() -> None:
    discover_modules("outerpkg.inner")
    assert "outerpkg" not in sys.modules


@pytest.mark.usefixtures("namespace")
def test_discover_modules_of_an_unknown_dotted_name() -> None:
    with pytest.raises(ModuleNotFoundError, match=r"No module named 'outerpkg\.nope'"):
        discover_modules("outerpkg.nope")


###############################
#     Tests for find_spec     #
###############################


@pytest.mark.usefixtures("pkg")
def test_find_spec_of_a_top_level_package() -> None:
    assert find_spec("discoverpkg") is not None


@pytest.mark.usefixtures("pkg")
def test_find_spec_of_a_dotted_name() -> None:
    assert find_spec("discoverpkg.sub.deep") is not None


@pytest.mark.usefixtures("pkg")
def test_find_spec_of_a_dotted_name_does_not_import_the_parents() -> None:
    find_spec("discoverpkg.sub.deep")
    assert "discoverpkg" not in sys.modules


@pytest.mark.usefixtures("pkg")
def test_find_spec_of_a_missing_part_is_none() -> None:
    assert find_spec("discoverpkg.sub.missing") is None


@pytest.mark.usefixtures("pkg")
def test_find_spec_below_a_module_is_none() -> None:
    assert find_spec("discoverpkg.a.deeper") is None


def test_find_spec_of_an_unknown_top_level_name_is_none() -> None:
    assert find_spec("no_such_pkg_xyz.sub") is None


###########################
#     Tests for _walk     #
###########################


def test_walk_returns_sorted_dotted_names(pkg: Path) -> None:
    assert _walk("p", [str(pkg)]) == ["p.a", "p.sub", "p.sub.b", "p.sub.deep"]


def test_walk_empty_directory(tmp_path: Path) -> None:
    assert _walk("p", [str(tmp_path)]) == []


##########################
#     Tests for main     #
##########################


def test_main_prints_one_module_per_line(pkg: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main([pkg.name])
    assert capsys.readouterr().out == (
        "discoverpkg\ndiscoverpkg.a\ndiscoverpkg.sub\ndiscoverpkg.sub.b\ndiscoverpkg.sub.deep\n"
    )


def test_main_success_exit_code(pkg: Path) -> None:
    assert main([pkg.name]) == 0


def test_main_unknown_package_exit_code() -> None:
    assert main(["no_such_pkg_xyz"]) == 1


def test_main_unknown_package_message(capsys: pytest.CaptureFixture[str]) -> None:
    main(["no_such_pkg_xyz"])
    assert capsys.readouterr().err == "No module named 'no_such_pkg_xyz'\n"


@pytest.mark.parametrize("argv", [[], ["a", "b"]])
def test_main_invalid_arguments_exit_code(argv: list[str]) -> None:
    assert main(argv) == 2


def test_main_invalid_arguments_usage(capsys: pytest.CaptureFixture[str]) -> None:
    main([])
    assert capsys.readouterr().err == "usage: python -m invoke_tasklib._discover <package>\n"


def test_running_the_module_exits_with_the_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["_discover", "no_such_pkg_xyz"])
    monkeypatch.delitem(sys.modules, "invoke_tasklib._discover")
    with pytest.raises(SystemExit, match=r"^1$") as exc_info:
        runpy.run_module("invoke_tasklib._discover", run_name="__main__")
    assert exc_info.value.code == 1
