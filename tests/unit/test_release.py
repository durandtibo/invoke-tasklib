from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit

from invoke_tasklib import release

if TYPE_CHECKING:
    from pathlib import Path


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


@pytest.fixture
def dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "mypkg-0.0.8-py3-none-any.whl").write_text("")
    (dist_dir / "mypkg-0.0.8.tar.gz").write_text("")
    monkeypatch.chdir(tmp_path)
    return dist_dir


_WHEEL_CHECK_CMD = (
    "uv run --isolated --no-project --with dist/mypkg-0.0.8-py3-none-any.whl -- "
    "python -c 'import mypkg'"
)
_SDIST_CHECK_CMD = (
    "uv run --isolated --no-project --with dist/mypkg-0.0.8.tar.gz -- python -c 'import mypkg'"
)

###########################
#     Tests for build     #
###########################


@pytest.mark.usefixtures("dist")
def test_build_without_check() -> None:
    c = _context({"package": {"name": "mypkg"}})
    release.build(c)
    assert _commands(c) == ["uv build", _WHEEL_CHECK_CMD, _SDIST_CHECK_CMD]


@pytest.mark.usefixtures("dist")
def test_build_with_check() -> None:
    c = _context({"package": {"name": "mypkg"}})
    release.build(c, check=True)
    assert _commands(c) == [
        "uv build",
        _WHEEL_CHECK_CMD,
        _SDIST_CHECK_CMD,
        "uvx twine check dist/*",
    ]


def test_build_installs_the_built_wheel_not_the_package_name(dist: Path) -> None:
    (dist / "mypkg-0.0.2-py3-none-any.whl").write_text("")
    os.utime(dist / "mypkg-0.0.2-py3-none-any.whl", (1, 1))
    c = _context({"package": {"name": "mypkg"}})
    release.build(c)
    assert _commands(c)[1] == _WHEEL_CHECK_CMD


def test_build_fails_when_no_wheel_is_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    c = _context({"package": {"name": "mypkg"}})
    with pytest.raises(Exit, match=r"No file matching '\*\.whl'"):
        release.build(c)


##########################
#     Tests for pypi     #
##########################


@pytest.mark.usefixtures("dist")
def test_pypi() -> None:
    c = _context({"package": {"name": "mypkg"}})
    release.pypi(c)
    assert _commands(c) == [
        "uv build",
        _WHEEL_CHECK_CMD,
        _SDIST_CHECK_CMD,
        "uv publish --token ${PYPI_TOKEN}",
    ]


######################################
#     Tests for _latest_artifact     #
######################################


def test_latest_artifact_returns_newest_file(tmp_path: Path) -> None:
    old = tmp_path / "a-0.0.2-py3-none-any.whl"
    new = tmp_path / "a-0.0.8-py3-none-any.whl"
    old.write_text("")
    new.write_text("")
    os.utime(old, (1, 1))
    assert release._latest_artifact(tmp_path, "*.whl") == new


def test_latest_artifact_ignores_other_patterns(tmp_path: Path) -> None:
    wheel = tmp_path / "a-1.0-py3-none-any.whl"
    wheel.write_text("")
    (tmp_path / "a-1.0.tar.gz").write_text("")
    assert release._latest_artifact(tmp_path, "*.whl") == wheel


def test_latest_artifact_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(Exit, match=r"No file matching '\*\.tar\.gz'"):
        release._latest_artifact(tmp_path, "*.tar.gz")
