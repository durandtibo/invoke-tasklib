from __future__ import annotations

import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from invoke.exceptions import Exit, UnexpectedExit

from invoke_tasklib import release
from invoke_tasklib.runner import run
from tests.integration.helpers import SubprocessContext, subprocess_context

if TYPE_CHECKING:
    from pathlib import Path


def _git(*args: str) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],  # noqa: S607
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "1.2.3"\n')
    _git("init", "-q")
    _git("add", ".")
    _git("commit", "-q", "-m", "init")
    return tmp_path


@pytest.mark.usefixtures("repo")
def test_check_release_state_accepts_a_tagged_clean_repository() -> None:
    _git("tag", "v1.2.3")
    assert release._check_release_state(subprocess_context()) is None


@pytest.mark.usefixtures("repo")
def test_check_release_state_rejects_an_untagged_repository() -> None:
    with pytest.raises(Exit, match=r"HEAD is not tagged"):
        release._check_release_state(subprocess_context())


def test_check_release_state_rejects_a_dirty_repository(repo: Path) -> None:
    _git("tag", "v1.2.3")
    (repo / "new.py").write_text("")
    with pytest.raises(Exit, match=r"working tree is not clean"):
        release._check_release_state(subprocess_context())


@pytest.mark.usefixtures("repo")
def test_check_release_state_rejects_a_wrong_tag() -> None:
    _git("tag", "v9.9.9")
    with pytest.raises(Exit, match=r"tag v9\.9\.9 does not match the version 1\.2\.3"):
        release._check_release_state(subprocess_context())


def test_confirm_without_a_terminal_asks_for_yes() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "from invoke_tasklib.release import _confirm; _confirm('PyPI')"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "Publication not confirmed: pass --yes" in result.stderr


###############################
#     Tests for the build     #
###############################

FLAT_PYPROJECT = """
[project]
name = "foo"
version = "0.1.0"
requires-python = ">=3.10"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["{packages}"]
"""


def _flat_project(root: Path, packages: str) -> None:
    (root / "foo").mkdir()
    (root / "foo" / "__init__.py").write_text("")
    (root / "pyproject.toml").write_text(FLAT_PYPROJECT.format(packages=packages))


def _build_context() -> SubprocessContext:
    return subprocess_context({"package": {"name": "foo"}})


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not installed")
def test_build_accepts_a_flat_layout_artifact_that_contains_the_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _flat_project(tmp_path, "foo")
    assert release.build(_build_context()) is None


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not installed")
def test_build_rejects_a_flat_layout_artifact_without_the_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _flat_project(tmp_path, "src/foo")
    with pytest.raises(UnexpectedExit, match=r"bad command exit code"):
        release.build(_build_context())


###########################################
#    Tests for the publish environment    #
###########################################


@pytest.fixture
def fake_uv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Put a ``uv`` that prints its credentials next to the
    interpreter, which is the first directory of the tool path."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text('#!/bin/sh\necho "token=${UV_PUBLISH_TOKEN:-none}"\n')
    uv.chmod(0o755)
    monkeypatch.setattr(sys, "executable", str(bin_dir / "python"))


@pytest.mark.usefixtures("fake_uv")
def test_publish_environment_does_not_leak_an_inherited_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UV_PUBLISH_TOKEN", "pypi-secret")
    result = run(
        subprocess_context(), "uv publish", env=release._publish_environment(None), replace_env=True
    )
    assert result.stdout == "token=none\n"


@pytest.mark.usefixtures("fake_uv")
def test_publish_environment_gives_the_chosen_token() -> None:
    result = run(
        subprocess_context(),
        "uv publish",
        env=release._publish_environment("chosen"),
        replace_env=True,
    )
    assert result.stdout == "token=chosen\n"


def test_check_release_state_names_the_line_of_an_invalid_pyproject(repo: Path) -> None:
    (repo / "pyproject.toml").write_text("[project\n")
    _git("commit", "-q", "-am", "break")
    _git("tag", "v1.2.3")
    with pytest.raises(Exit, match=r"invalid TOML in 'pyproject\.toml' \(line 1, column 9\)"):
        release._check_release_state(subprocess_context())
