from __future__ import annotations

import shlex
import subprocess
from typing import TYPE_CHECKING

import pytest
from invoke.config import Config
from invoke.context import Context
from invoke.exceptions import Exit, UnexpectedExit
from invoke.runners import Result

from invoke_tasklib import imports

if TYPE_CHECKING:
    from pathlib import Path


class _SubprocessContext(Context):
    r"""A context that really runs the commands, not Invoke's runner.

    Invoke's local runner leaves file handles open under pytest, which
    pytest reports as unraisable warnings in unrelated tests.
    """

    def run(self, command: str, **kwargs: object) -> Result:
        proc = subprocess.run(  # noqa: S603 (commands are built by the tasks under test)
            shlex.split(command), capture_output=True, text=True, check=False
        )
        result = Result(stdout=proc.stdout, stderr=proc.stderr, exited=proc.returncode)
        if proc.returncode and not kwargs.get("warn"):
            raise UnexpectedExit(result)
        return result


def _context(name: str) -> Context:
    return _SubprocessContext(config=Config(overrides={"tasklib": {"package": {"name": name}}}))


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


####################################
#     Tests for check_isolated     #
####################################


def test_check_isolated_passes_without_cycle(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(
        project,
        {
            "okpkg/__init__.py": "",
            "okpkg/a.py": "from okpkg import b\n",
            "okpkg/b.py": "X = 1\n",
        },
    )
    imports.check_isolated(_context("okpkg"))
    assert "✅ All 3 module(s) imported on their own" in capsys.readouterr().out


def test_check_isolated_detects_cycle_between_sibling_modules(project: Path) -> None:
    _write(
        project,
        {
            "cycpkg/__init__.py": "",
            "cycpkg/a.py": "from cycpkg.b import Y\nX = 1\n",
            "cycpkg/b.py": "from cycpkg.a import X\nY = 2\n",
        },
    )
    with pytest.raises(Exit, match=r"^2 of 3 module\(s\) failed to import on their own$"):
        imports.check_isolated(_context("cycpkg"))


def test_check_isolated_lists_the_error_of_each_failed_module(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(
        project,
        {
            "errpkg/__init__.py": "",
            "errpkg/bad.py": "import not_installed_anywhere_xyz\n",
            "errpkg/good.py": "X = 1\n",
        },
    )
    with pytest.raises(Exit, match=r"^1 of 3 module"):
        imports.check_isolated(_context("errpkg"))
    err = capsys.readouterr().err
    assert "❌ errpkg.bad: ModuleNotFoundError: No module named 'not_installed_anywhere_xyz'" in err


def test_check_isolated_does_not_echo_one_command_per_module(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(project, {"quietpkg/__init__.py": "", "quietpkg/a.py": "", "quietpkg/b.py": ""})
    imports.check_isolated(_context("quietpkg"))
    assert capsys.readouterr().out == (
        "🔍 Importing each module of quietpkg in its own interpreter...\n"
        "✅ All 3 module(s) imported on their own\n"
    )


##################################
#     Tests for check_cycles     #
##################################


def test_check_cycles_reports_a_cycle_without_importing_anything(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(
        project,
        {
            "stcpkg/__init__.py": "raise RuntimeError('imported')\n",
            "stcpkg/a.py": "from stcpkg import b\n",
            "stcpkg/b.py": "from stcpkg import a\n",
        },
    )
    monkeypatch.syspath_prepend(str(project))
    with pytest.raises(Exit, match=r"stcpkg\.a -> stcpkg\.b -> stcpkg\.a"):
        imports.check_cycles(_context("stcpkg"))


def test_check_cycles_reports_a_relative_import_above_the_top_level_package(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(project, {"relpkg/__init__.py": "", "relpkg/a.py": "from .. import x\n"})
    monkeypatch.syspath_prepend(str(project))
    msg = r"Cannot parse module relpkg\.a: attempted relative import beyond top-level package"
    with pytest.raises(Exit, match=msg):
        imports.check_cycles(_context("relpkg"))


def test_check_cycles_reports_the_cycle_that_import_order_hides(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(
        project,
        {
            "hidpkg/__init__.py": "",
            "hidpkg/a.py": "import hidpkg.b\nX = 1\n",
            "hidpkg/b.py": "import hidpkg.a\nY = 2\n",
        },
    )
    monkeypatch.syspath_prepend(str(project))
    imports.check_isolated(_context("hidpkg"))
    with pytest.raises(Exit, match=r"Found 1 import cycle"):
        imports.check_cycles(_context("hidpkg"))


def test_check_isolated_checks_many_modules(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {f"bigpkg/m{i}.py": "X = 1\n" for i in range(40)}
    _write(project, {"bigpkg/__init__.py": "", **files})
    imports.check_isolated(_context("bigpkg"))
    assert "✅ All 41 module(s) imported on their own" in capsys.readouterr().out


def test_check_isolated_lists_the_failures_in_the_order_of_the_modules(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {f"orderpkg/m{i}.py": "raise RuntimeError('boom')\n" for i in (3, 1, 2)}
    _write(project, {"orderpkg/__init__.py": "", **files})
    with pytest.raises(Exit, match=r"^3 of 4 module"):
        imports.check_isolated(_context("orderpkg"))
    assert capsys.readouterr().err == (
        "❌ orderpkg.m1: RuntimeError: boom\n"
        "❌ orderpkg.m2: RuntimeError: boom\n"
        "❌ orderpkg.m3: RuntimeError: boom\n"
        "❌ Failed: Checking that each module imports on its own\n"
    )
