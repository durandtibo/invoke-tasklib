from __future__ import annotations

import shlex
import subprocess
from typing import TYPE_CHECKING

import pytest
from invoke.config import Config
from invoke.context import Context
from invoke.exceptions import UnexpectedExit
from invoke.runners import Result

from invoke_tasklib import imports

if TYPE_CHECKING:
    from pathlib import Path


class _SubprocessContext(Context):
    r"""A context that really runs the commands, not Invoke's runner.

    Invoke's local runner leaves file handles open under pytest, which
    pytest reports as unraisable warnings in unrelated tests.
    """

    def run(self, command: str, **_kwargs: object) -> Result:
        proc = subprocess.run(  # noqa: S603 (commands are built by the tasks under test)
            shlex.split(command), capture_output=True, text=True, check=False
        )
        result = Result(stdout=proc.stdout, stderr=proc.stderr, exited=proc.returncode)
        if proc.returncode:
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


##################################
#     Tests for check_cycles     #
##################################


def test_check_cycles_passes_without_cycle(project: Path) -> None:
    _write(
        project,
        {
            "okpkg/__init__.py": "",
            "okpkg/a.py": "from okpkg import b\n",
            "okpkg/b.py": "X = 1\n",
        },
    )
    imports.check_cycles(_context("okpkg"))


def test_check_cycles_detects_cycle_between_sibling_modules(project: Path) -> None:
    _write(
        project,
        {
            "cycpkg/__init__.py": "",
            "cycpkg/a.py": "from cycpkg.b import Y\nX = 1\n",
            "cycpkg/b.py": "from cycpkg.a import X\nY = 2\n",
        },
    )
    with pytest.raises(UnexpectedExit):
        imports.check_cycles(_context("cycpkg"))
