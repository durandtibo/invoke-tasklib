from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _all_programs_available(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Make the unit tests independent of the tools installed on the
    machine: every program is found on the ``PATH``."""
    monkeypatch.setattr(
        "invoke_tasklib.tools.shutil.which", lambda program, **_kwargs: f"/bin/{program}"
    )


@pytest.fixture(autouse=True)
def _not_on_github_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Make the unit tests independent of the CI: ruff does not use the
    ``github`` output format."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


@pytest.fixture
def default_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r"""A project with the default paths of ``mypkg``, as the working
    directory: ``src/mypkg``, ``tests/unit`` and ``docs/mkdocs.yml``."""
    (tmp_path / "src" / "mypkg").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "mkdocs.yml").write_text("site_name: mypkg\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path
