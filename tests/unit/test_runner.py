from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from invoke_tasklib.runner import python_executable

if TYPE_CHECKING:
    import pytest

#######################################
#     Tests for python_executable     #
#######################################


def test_python_executable_returns_running_interpreter() -> None:
    assert python_executable() == sys.executable


def test_python_executable_quotes_path_with_space(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/my env/bin/python")
    assert python_executable() == "'/my env/bin/python'"
