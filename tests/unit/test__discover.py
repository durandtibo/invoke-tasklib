from __future__ import annotations

import importlib
import runpy
import sys
from typing import TYPE_CHECKING

import pytest

from invoke_tasklib._discover import _walk, discover_modules, main

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
