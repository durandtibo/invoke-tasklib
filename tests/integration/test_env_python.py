from __future__ import annotations

import os
import shutil
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
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    env.show_python_config(subprocess_context())
    assert capsys.readouterr().out.splitlines()[-1] == str(fake)
