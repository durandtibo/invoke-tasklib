from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _empty_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Resolve the config in an empty project, so the defaults read
    from the files (the Python version) do not depend on this repo."""
    monkeypatch.chdir(tmp_path)
