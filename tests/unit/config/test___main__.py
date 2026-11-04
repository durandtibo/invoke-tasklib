from __future__ import annotations

import json
import runpy
import sys

import pytest


@pytest.fixture(autouse=True)
def _fresh_module(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Run the module from scratch, as a bare call."""
    monkeypatch.setattr(sys, "argv", ["config"])
    monkeypatch.delitem(sys.modules, "invoke_tasklib.config")


def test_running_the_module_exits_with_code_0() -> None:
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("invoke_tasklib.config", run_name="__main__")
    assert exc_info.value.code == 0


def test_running_the_module_prints_the_schema(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match=r"0"):
        runpy.run_module("invoke_tasklib.config", run_name="__main__")
    assert json.loads(capsys.readouterr().out)["title"] == "invoke.yaml of invoke-tasklib"


def test_importing_the_main_module_prints_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    runpy.run_module("invoke_tasklib.config.__main__", run_name="not_main")
    assert capsys.readouterr().out == ""
