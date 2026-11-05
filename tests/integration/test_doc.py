from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from functools import partial
from pathlib import Path

import pytest
from invoke.exceptions import Exit

from invoke_tasklib import doc
from tests.integration.helpers import subprocess_context

GIT = shutil.which("git") or "git"


def _git(*args: str) -> str:
    return subprocess.run(  # noqa: S603
        [GIT, *args], capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{name}_NAME", "Tester")
        monkeypatch.setenv(f"GIT_{name}_EMAIL", "tester@example.com")
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}")
    if shutil.which("mike") is None:
        reason = "mike is not installed: install the 'docs' group with `uv sync --group docs`"
        if os.environ.get("REQUIRE_MIKE") == "true":
            pytest.fail(reason)
        pytest.skip(reason)
    monkeypatch.chdir(tmp_path)
    _git("init", "-q")
    (tmp_path / "mkdocs.yml").write_text("site_name: demo\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# Demo\n")
    _git("add", "-A")
    _git("commit", "-q", "-m", "init")
    return tmp_path


_context = partial(
    subprocess_context, {"package": {"name": "demo"}, "paths": {"docs_config": "mkdocs.yml"}}
)


def _published() -> list[str]:
    return [entry["version"] for entry in json.loads(_git("show", "gh-pages:versions.json"))]


###################################
#     Tests for _last_version_tag     #
###################################


@pytest.mark.usefixtures("repo")
def test_last_version_tag_without_tag_is_none() -> None:
    assert doc._last_version_tag(_context()) is None


@pytest.fixture
def tags(request: pytest.FixtureRequest) -> None:
    r"""Create the git tags given by the parameter in the ``repo``."""
    request.getfixturevalue("repo")
    for tag in request.param:
        _git("tag", tag)


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        (("v1.2.0", "v1.10.0", "v1.9.5", "not-a-version"), "v1.10.0"),
        (("v1.2.0", "v1.2.0rc1", "v1.1.0"), "v1.2.0"),
        (("v1.3.0rc1", "v1.2.0"), "v1.2.0"),
        (("v1.2.0", "v1.3.0-backport"), "v1.3.0-backport"),
    ],
    indirect=["tags"],
)
@pytest.mark.usefixtures("tags")
def test_last_version_tag_returns_the_highest_release(expected: str) -> None:
    assert doc._last_version_tag(_context()) == expected


#####################################
#     Tests for publish_latest     #
#####################################


@pytest.mark.usefixtures("repo")
def test_publish_latest_without_push_publishes_the_version() -> None:
    doc.publish_latest(_context(), version="1.2.0", push=False)
    assert _published() == ["1.2"]


@pytest.mark.usefixtures("repo")
def test_publish_latest_refuses_an_older_version() -> None:
    doc.publish_latest(_context(), version="1.2.0", push=False)
    with pytest.raises(Exit, match=r"Refusing to publish 1\.1 as latest"):
        doc.publish_latest(_context(), version="1.1.5", push=False)


@pytest.mark.usefixtures("repo")
def test_publish_latest_refusal_keeps_the_published_versions() -> None:
    doc.publish_latest(_context(), version="1.2.0", push=False)
    with pytest.raises(Exit, match=r"Refusing to publish"):
        doc.publish_latest(_context(), version="1.1.5", push=False)
    assert _published() == ["1.2"]


@pytest.mark.usefixtures("repo")
def test_publish_latest_force_publishes_an_older_version() -> None:
    doc.publish_latest(_context(), version="1.2.0", push=False)
    doc.publish_latest(_context(), version="1.1.5", push=False, force=True)
    assert sorted(_published()) == ["1.1", "1.2"]


@pytest.mark.usefixtures("repo")
def test_publish_latest_uses_the_last_git_tag() -> None:
    _git("tag", "v1.3.0")
    doc.publish_latest(_context(), push=False)
    assert _published() == ["1.3"]


@pytest.mark.usefixtures("repo")
def test_published_releases_lists_what_mike_published() -> None:
    doc.publish_latest(_context(), version="1.2.0", push=False)
    assert doc._published_releases(_context(), "mkdocs.yml") == [(1, 2)]


@pytest.mark.usefixtures("repo")
def test_published_releases_is_empty_before_any_publication() -> None:
    assert doc._published_releases(_context(), "mkdocs.yml") == []


@pytest.mark.usefixtures("repo")
def test_publish_dev_without_push_can_be_run_twice() -> None:
    doc.publish_dev(_context(), push=False)
    doc.publish_dev(_context(), push=False)
    assert _published() == ["main"]
