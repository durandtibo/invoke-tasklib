from __future__ import annotations

import os
import shutil
import sys
from typing import TYPE_CHECKING

import pytest

from invoke_tasklib import env
from tests.integration.helpers import subprocess_context

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not installed")


########################################
#     Tests for show_python_config     #
########################################


def test_show_python_config_prints_the_python_of_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = tmp_path / "python"
    # uv runs the python of the PATH to query it, so it must work
    fake.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    env.show_python_config(subprocess_context())
    assert capsys.readouterr().out.splitlines()[-1] == str(fake)


def test_show_python_config_accepts_a_pinned_version_that_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".python-version").write_text("2.6\n")
    monkeypatch.chdir(tmp_path)
    env.show_python_config(subprocess_context())
    assert "Python configuration" in capsys.readouterr().out
