from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit
from invoke.runners import Result

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
    assert _commands(c) == ["uv build --clear", _WHEEL_CHECK_CMD, _SDIST_CHECK_CMD]


@pytest.mark.usefixtures("dist")
def test_build_with_args() -> None:
    c = _context({"package": {"name": "mypkg"}})
    release.build(c, args="--no-sources")
    assert _commands(c)[0] == "uv build --clear --no-sources"


@pytest.mark.usefixtures("dist")
def test_build_imports_the_import_name() -> None:
    c = _context({"package": {"name": "my-pkg"}})
    release.build(c)
    assert _commands(c)[1].endswith("-- python -c 'import my_pkg'")


@pytest.mark.usefixtures("dist")
def test_build_imports_the_configured_import_name() -> None:
    c = _context({"package": {"name": "my-pkg", "import_name": "other"}})
    release.build(c)
    assert _commands(c)[2].endswith("-- python -c 'import other'")


@pytest.mark.usefixtures("dist")
def test_build_with_check() -> None:
    c = _context({"package": {"name": "mypkg"}})
    release.build(c, check=True)
    assert _commands(c) == [
        "uv build --clear",
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


#############################
#     Tests for publish     #
#############################

_CFG = {"package": {"name": "mypkg"}}
_BUILD = ["uv build --clear", _WHEEL_CHECK_CMD, _SDIST_CHECK_CMD]


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "PYPI_TOKEN",
        "UV_PUBLISH_TOKEN",
        "GITHUB_ACTIONS",
        "ACTIONS_ID_TOKEN_REQUEST_URL",
        "CI",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYPI_TOKEN", "pypi-secret")


@pytest.fixture
def oidc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://token.example")


@pytest.mark.usefixtures("dist", "token")
def test_publish() -> None:
    c = _context(_CFG)
    release.publish(c, yes=True, skip_checks=True)
    assert _commands(c) == [*_BUILD, "uv publish"]


@pytest.mark.usefixtures("dist", "token")
def test_publish_args_go_to_publish_not_to_build() -> None:
    c = _context(_CFG)
    release.publish(c, yes=True, skip_checks=True, args="--index testpypi")
    assert _commands(c) == [*_BUILD, "uv publish --index testpypi"]


@pytest.mark.usefixtures("dist", "token")
def test_publish_to_test_pypi() -> None:
    c = _context(_CFG)
    release.publish(c, test_pypi=True, yes=True, skip_checks=True)
    assert _commands(c)[-1] == (
        "uv publish --publish-url https://test.pypi.org/legacy/ "
        "--check-url https://test.pypi.org/simple/"
    )


@pytest.mark.usefixtures("dist", "token")
def test_publish_dry_run() -> None:
    c = _context(_CFG)
    release.publish(c, dry_run=True, skip_checks=True)
    assert _commands(c) == [*_BUILD, "uv publish --dry-run"]


@pytest.mark.usefixtures("dist")
def test_publish_dry_run_needs_no_credentials() -> None:
    c = _context(_CFG)
    release.publish(c, dry_run=True, skip_checks=True)
    assert _commands(c)[-1] == "uv publish --dry-run"


@pytest.mark.usefixtures("dist", "token")
def test_publish_passes_token_through_environment() -> None:
    c = _context(_CFG)
    release.publish(c, yes=True, skip_checks=True)
    run = c.run
    assert isinstance(run, Mock)
    assert run.call_args.kwargs["env"] == {"UV_PUBLISH_TOKEN": "pypi-secret"}


@pytest.mark.usefixtures("dist", "token")
def test_publish_does_not_put_token_on_command_line() -> None:
    c = _context(_CFG)
    release.publish(c, yes=True, skip_checks=True)
    assert "pypi-secret" not in " ".join(_commands(c))


@pytest.mark.usefixtures("dist")
def test_publish_accepts_uv_publish_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UV_PUBLISH_TOKEN", "uv-secret")
    c = _context(_CFG)
    release.publish(c, yes=True, skip_checks=True)
    run = c.run
    assert isinstance(run, Mock)
    assert run.call_args.kwargs["env"] == {"UV_PUBLISH_TOKEN": "uv-secret"}


@pytest.mark.usefixtures("dist", "oidc")
def test_publish_uses_trusted_publishing_without_token() -> None:
    c = _context(_CFG)
    release.publish(c, yes=True, skip_checks=True)
    assert _commands(c)[-1] == "uv publish --trusted-publishing always"


@pytest.mark.usefixtures("dist", "oidc")
def test_publish_sends_no_token_with_trusted_publishing() -> None:
    c = _context(_CFG)
    release.publish(c, yes=True, skip_checks=True)
    run = c.run
    assert isinstance(run, Mock)
    assert run.call_args.kwargs["env"] == {}


@pytest.mark.usefixtures("dist", "oidc", "token")
def test_publish_prefers_the_token_to_trusted_publishing() -> None:
    c = _context(_CFG)
    release.publish(c, yes=True, skip_checks=True)
    assert _commands(c)[-1] == "uv publish"


@pytest.mark.usefixtures("dist")
def test_publish_requires_the_id_token_url_for_trusted_publishing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(Exit, match=r"PYPI_TOKEN"):
        release.publish(_context(_CFG), yes=True, skip_checks=True)


def test_publish_fails_without_credentials() -> None:
    with pytest.raises(Exit, match=r"PYPI_TOKEN"):
        release.publish(_context(_CFG))


def test_publish_does_not_build_without_credentials() -> None:
    c = _context(_CFG)
    with pytest.raises(Exit, match=r"PYPI_TOKEN"):
        release.publish(c)
    assert _commands(c) == []


@pytest.mark.usefixtures("dist", "token")
def test_publish_asks_for_a_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    c = _context(_CFG)
    with pytest.raises(Exit, match=r"Publication cancelled"):
        release.publish(c, skip_checks=True)
    assert _commands(c) == []


@pytest.mark.usefixtures("dist", "token")
def test_publish_goes_on_after_a_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    c = _context(_CFG)
    release.publish(c, skip_checks=True)
    assert _commands(c)[-1] == "uv publish"


@pytest.mark.usefixtures("dist", "token")
def test_publish_does_not_ask_in_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")
    c = _context(_CFG)
    release.publish(c, skip_checks=True)
    assert _commands(c)[-1] == "uv publish"


@pytest.mark.usefixtures("dist", "token")
def test_publish_checks_the_git_state_first() -> None:
    c = _git_context(status=" M a.py\n")
    with pytest.raises(Exit, match=r"working tree is not clean"):
        release.publish(c, yes=True)
    assert _commands(c) == ["git status --porcelain"]


##########################################
#     Tests for _check_release_state     #
##########################################

_DESCRIBE = "git describe --exact-match --tags HEAD"


def _git_context(status: str = "", tag: str | None = "v1.2.3") -> MockContext:
    describe = Result(stdout=f"{tag}\n") if tag else Result(exited=128)
    return MockContext(
        config=Config(overrides={"tasklib": _CFG}),
        run={"git status --porcelain": Result(stdout=status), _DESCRIBE: describe},
    )


@pytest.fixture
def project_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\nversion = "1.2.3"\n')
    monkeypatch.chdir(tmp_path)


@pytest.mark.usefixtures("project_version")
def test_check_release_state_accepts_a_clean_tagged_matching_state() -> None:
    assert release._check_release_state(_git_context()) is None


@pytest.mark.usefixtures("project_version")
def test_check_release_state_rejects_a_dirty_tree() -> None:
    with pytest.raises(Exit, match=r"working tree is not clean"):
        release._check_release_state(_git_context(status="?? new.py\n"))


@pytest.mark.usefixtures("project_version")
def test_check_release_state_rejects_an_untagged_head() -> None:
    with pytest.raises(Exit, match=r"HEAD is not tagged"):
        release._check_release_state(_git_context(tag=None))


@pytest.mark.usefixtures("project_version")
def test_check_release_state_rejects_a_tag_that_does_not_match_the_version() -> None:
    with pytest.raises(Exit, match=r"tag v1\.2\.4 does not match the version 1\.2\.3"):
        release._check_release_state(_git_context(tag="v1.2.4"))


@pytest.mark.usefixtures("project_version")
def test_check_release_state_accepts_a_tag_without_prefix() -> None:
    assert release._check_release_state(_git_context(tag="1.2.3")) is None


def test_check_release_state_skips_the_version_without_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert release._check_release_state(_git_context(tag="v9.9.9")) is None


######################################
#     Tests for _project_version     #
######################################


def test_project_version_reads_the_static_version(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nversion = "0.4.0"\n')
    assert release._project_version(path) == "0.4.0"


def test_project_version_is_none_for_a_dynamic_version(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\ndynamic = ["version"]\n')
    assert release._project_version(path) is None


def test_project_version_is_none_without_project_table(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text("[tool.x]\na = 1\n")
    assert release._project_version(path) is None


def test_project_version_is_none_for_a_missing_file(tmp_path: Path) -> None:
    assert release._project_version(tmp_path / "pyproject.toml") is None


###############################
#     Tests for _head_tag     #
###############################


def test_head_tag_returns_the_tag() -> None:
    assert release._head_tag(_git_context(tag="v2.0.0")) == "v2.0.0"


def test_head_tag_is_none_when_git_fails() -> None:
    assert release._head_tag(_git_context(tag=None)) is None


##############################
#     Tests for _confirm     #
##############################


@pytest.mark.parametrize("answer", ["y", "yes", "Y", " YES "])
def test_confirm_accepts(answer: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{answer}\n"))
    assert release._confirm("PyPI") is None


@pytest.mark.parametrize("answer", ["", "n", "no", "maybe"])
def test_confirm_refuses(answer: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{answer}\n"))
    with pytest.raises(Exit, match=r"Publication cancelled"):
        release._confirm("PyPI")


def test_confirm_names_the_target(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    release._confirm("TestPyPI")
    assert "Publish the package to TestPyPI?" in capsys.readouterr().out


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
