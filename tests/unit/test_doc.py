from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit
from invoke.runners import Result

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch

from invoke_tasklib import doc
from invoke_tasklib.doc import _docs_config, _parse_release, _parse_releases, _published_releases


@pytest.fixture(autouse=True)
def _docs_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "mkdocs.yml").write_text("")
    (tmp_path / "mkdocs.yml").write_text("")
    (tmp_path / "d d").mkdir()
    (tmp_path / "d d" / "mkdocs.yml").write_text("")
    monkeypatch.chdir(tmp_path)


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


#################################
#     Tests for publish_dev     #
#################################


def test_publish_dev() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "docs/mkdocs.yml"}})
    doc.publish_dev(c)
    assert _commands(c) == [
        "mike deploy --config-file docs/mkdocs.yml --push --update-aliases main dev"
    ]


def test_publish_dev_does_not_delete_the_version_first() -> None:
    c = _context(_DOCS)
    doc.publish_dev(c)
    assert not any(command.startswith("mike delete") for command in _commands(c))


def test_publish_dev_without_push() -> None:
    c = _context(_DOCS)
    doc.publish_dev(c, push=False)
    assert _commands(c) == ["mike deploy --config-file docs/mkdocs.yml --update-aliases main dev"]


def test_publish_dev_quotes_the_docs_config() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "d d/mkdocs.yml"}})
    doc.publish_dev(c)
    assert _commands(c) == [
        "mike deploy --config-file 'd d/mkdocs.yml' --push --update-aliases main dev"
    ]


####################################
#     Tests for publish_latest     #
####################################

_DOCS = {"package": {"name": "mypkg"}, "paths": {"docs_config": "docs/mkdocs.yml"}}
_DEPLOY_1_2 = [
    "mike deploy --config-file docs/mkdocs.yml --push --update-aliases 1.2 latest",
    "mike set-default --config-file docs/mkdocs.yml --push --allow-empty latest",
]


def _git_tag(monkeypatch: MonkeyPatch, tag: str | None) -> None:
    monkeypatch.setattr(doc, "_last_version_tag", lambda _c: tag)


def _published(monkeypatch: MonkeyPatch, *releases: tuple[int, int]) -> None:
    monkeypatch.setattr(doc, "_published_releases", lambda _c, _config: list(releases))


@pytest.fixture(autouse=True)
def _nothing_published(monkeypatch: MonkeyPatch) -> None:
    _published(monkeypatch)


def test_publish_latest_uses_last_version_tag(monkeypatch: MonkeyPatch) -> None:
    _git_tag(monkeypatch, "v1.2.3")
    c = _context(_DOCS)
    doc.publish_latest(c)
    assert _commands(c) == _DEPLOY_1_2


def test_publish_latest_quotes_the_docs_config() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "d d/mkdocs.yml"}})
    doc.publish_latest(c, version="1.2.3")
    assert _commands(c) == [
        "mike deploy --config-file 'd d/mkdocs.yml' --push --update-aliases 1.2 latest",
        "mike set-default --config-file 'd d/mkdocs.yml' --push --allow-empty latest",
    ]


def test_publish_latest_without_push() -> None:
    c = _context(_DOCS)
    doc.publish_latest(c, version="1.2.3", push=False)
    assert _commands(c) == [
        "mike deploy --config-file docs/mkdocs.yml --update-aliases 1.2 latest",
        "mike set-default --config-file docs/mkdocs.yml --allow-empty latest",
    ]


def test_publish_latest_does_not_delete_the_version_first(monkeypatch: MonkeyPatch) -> None:
    _git_tag(monkeypatch, "v1.2.3")
    c = _context(_DOCS)
    doc.publish_latest(c)
    assert not any(command.startswith("mike delete") for command in _commands(c))


def test_publish_latest_fails_when_no_tag(monkeypatch: MonkeyPatch) -> None:
    _git_tag(monkeypatch, None)
    c = _context(_DOCS)
    with pytest.raises(Exit, match=r"No version tag found"):
        doc.publish_latest(c)


def test_publish_latest_does_not_publish_when_no_tag(monkeypatch: MonkeyPatch) -> None:
    _git_tag(monkeypatch, None)
    c = _context(_DOCS)
    with pytest.raises(Exit, match=r"No version tag found"):
        doc.publish_latest(c)
    assert _commands(c) == []


@pytest.mark.parametrize("tag", ["v1.2.0rc1", "v1.2.0a1", "v1.2.0b2", "v1.2.0.dev3"])
def test_publish_latest_skips_pre_release_tag(monkeypatch: MonkeyPatch, tag: str) -> None:
    _git_tag(monkeypatch, tag)
    c = _context(_DOCS)
    doc.publish_latest(c)
    assert _commands(c) == []


def test_publish_latest_reports_skipped_pre_release(
    monkeypatch: MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _git_tag(monkeypatch, "v1.2.0rc1")
    doc.publish_latest(_context(_DOCS))
    assert capsys.readouterr().out == (
        "⏭️  Skipping the pre-release version v1.2.0rc1: latest docs not published\n"
    )


def test_publish_latest_with_explicit_version_does_not_read_the_git_tags(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(doc, "_last_version_tag", lambda _c: pytest.fail("tags were read"))
    c = _context(_DOCS)
    doc.publish_latest(c, version="1.2.3")
    assert _commands(c) == _DEPLOY_1_2


def test_publish_latest_explicit_version_wins_over_tag(monkeypatch: MonkeyPatch) -> None:
    _git_tag(monkeypatch, "v3.0.0")
    c = _context(_DOCS)
    doc.publish_latest(c, version="1.2")
    assert _commands(c) == _DEPLOY_1_2


def test_publish_latest_explicit_pre_release_is_skipped() -> None:
    c = _context(_DOCS)
    doc.publish_latest(c, version="1.2.0rc1")
    assert _commands(c) == []


def test_publish_latest_fails_on_unparsable_version() -> None:
    c = _context(_DOCS)
    with pytest.raises(Exit, match=r"Cannot parse the version 'latest'"):
        doc.publish_latest(c, version="latest")


def test_publish_latest_does_not_import_packaging(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "packaging", None)
    monkeypatch.setitem(sys.modules, "packaging.version", None)
    c = _context(_DOCS)
    doc.publish_latest(c, version="1.2.3")
    assert _commands(c) == _DEPLOY_1_2


def test_publish_latest_refuses_to_move_latest_backwards(monkeypatch: MonkeyPatch) -> None:
    _published(monkeypatch, (1, 0), (1, 2))
    c = _context(_DOCS)
    with pytest.raises(
        Exit, match=r"Refusing to publish 1\.1 as latest: 1\.2 is already published"
    ):
        doc.publish_latest(c, version="1.1.5")


def test_publish_latest_refusal_runs_nothing(monkeypatch: MonkeyPatch) -> None:
    _published(monkeypatch, (1, 2))
    c = _context(_DOCS)
    with pytest.raises(Exit, match=r"Refusing to publish"):
        doc.publish_latest(c, version="1.1.5")
    assert _commands(c) == []


def test_publish_latest_refusal_mentions_force(monkeypatch: MonkeyPatch) -> None:
    _published(monkeypatch, (1, 2))
    with pytest.raises(Exit, match=r"Use --force"):
        doc.publish_latest(_context(_DOCS), version="1.1.5")


def test_publish_latest_force_publishes_an_older_version(monkeypatch: MonkeyPatch) -> None:
    _published(monkeypatch, (1, 2))
    c = _context(_DOCS)
    doc.publish_latest(c, version="1.1.5", force=True)
    assert _commands(c) == [
        "mike deploy --config-file docs/mkdocs.yml --push --update-aliases 1.1 latest",
        "mike set-default --config-file docs/mkdocs.yml --push --allow-empty latest",
    ]


def test_publish_latest_republishes_the_newest_version(monkeypatch: MonkeyPatch) -> None:
    _published(monkeypatch, (1, 1), (1, 2))
    c = _context(_DOCS)
    doc.publish_latest(c, version="1.2.4")
    assert _commands(c) == _DEPLOY_1_2


def test_publish_latest_publishes_a_newer_version(monkeypatch: MonkeyPatch) -> None:
    _published(monkeypatch, (1, 1))
    c = _context(_DOCS)
    doc.publish_latest(c, version="1.2.0")
    assert _commands(c) == _DEPLOY_1_2


def test_publish_latest_compares_minor_versions_as_numbers(monkeypatch: MonkeyPatch) -> None:
    _published(monkeypatch, (1, 9))
    c = _context(_DOCS)
    doc.publish_latest(c, version="1.10.0")
    assert _commands(c) == [
        "mike deploy --config-file docs/mkdocs.yml --push --update-aliases 1.10 latest",
        "mike set-default --config-file docs/mkdocs.yml --push --allow-empty latest",
    ]


def test_publish_latest_does_not_check_the_published_versions_of_a_pre_release(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(doc, "_published_releases", lambda _c, _config: pytest.fail("listed"))
    doc.publish_latest(_context(_DOCS), version="1.0.0rc1")


#######################################
#     Tests for _last_version_tag     #
#######################################

_TAG_COMMAND = "git tag --list 'v[0-9]*' --sort=-v:refname"


def _git(stdout: str) -> MockContext:
    return MockContext(config=Config(), run={_TAG_COMMAND: Result(stdout=stdout)})


def test_last_version_tag_returns_the_first_tag() -> None:
    assert doc._last_version_tag(_git("v1.2.0\nv1.1.0\n")) == "v1.2.0"


def test_last_version_tag_without_tag_is_none() -> None:
    assert doc._last_version_tag(_git("")) is None


def test_last_version_tag_skips_a_tag_that_is_not_a_version() -> None:
    assert doc._last_version_tag(_git("v2beta\nv1.1.0\n")) == "v1.1.0"


def test_last_version_tag_keeps_a_pre_release_tag() -> None:
    assert doc._last_version_tag(_git("v1.3.0rc1\nv1.2.0\n")) == "v1.3.0rc1"


#########################################
#     Tests for _published_releases     #
#########################################


def _mike(stdout: str) -> MockContext:
    command = "mike list --config-file docs/mkdocs.yml --json"
    return MockContext(config=Config(), run={command: Result(stdout=stdout)})


def test_published_releases_reads_the_versions() -> None:
    out = '[{"version": "main", "aliases": ["dev"]}, {"version": "1.2"}, {"version": "1.10"}]'
    assert _published_releases(_mike(out), "docs/mkdocs.yml") == [(1, 2), (1, 10)]


def test_published_releases_without_output_is_empty() -> None:
    assert _published_releases(_mike(""), "docs/mkdocs.yml") == []


def test_published_releases_without_version_is_empty() -> None:
    assert _published_releases(_mike("[]"), "docs/mkdocs.yml") == []


@pytest.mark.parametrize("out", ["not json", '{"version": "1.2"}', '[{"title": "1.2"}]', "[1]"])
def test_published_releases_rejects_an_unexpected_output(out: str) -> None:
    with pytest.raises(Exit, match=r"Cannot read the output of 'mike list"):
        _published_releases(_mike(out), "docs/mkdocs.yml")


def test_parse_releases_reads_the_versions() -> None:
    assert _parse_releases('[{"version": "1.2"}, {"version": "main"}]', "cmd") == [(1, 2)]


def test_parse_releases_error_names_the_command() -> None:
    with pytest.raises(Exit, match=r"Cannot read the output of 'mike list --json': 'oops'"):
        _parse_releases("oops", "mike list --json")


def test_parse_releases_keeps_the_order() -> None:
    assert _parse_releases('[{"version": "1.10"}, {"version": "1.2"}]', "cmd") == [(1, 10), (1, 2)]


def test_published_releases_quotes_the_docs_config() -> None:
    command = "mike list --config-file 'd d/mkdocs.yml' --json"
    c = MockContext(config=Config(), run={command: Result(stdout="[]")})
    assert _published_releases(c, "d d/mkdocs.yml") == []


##################################
#     Tests for _release_key     #
##################################


@pytest.mark.parametrize(
    ("tag", "expected"),
    [("1.2", (1, 2)), ("1.10", (1, 10)), ("v2.0.1", (2, 0)), ("main", None), ("dev", None)],
)
def test_release_key(tag: str, expected: tuple[int, int] | None) -> None:
    assert doc._release_key(tag) == expected


##################################
#     Tests for _push_option     #
##################################


def test_push_option_with_push() -> None:
    assert doc._push_option(push=True) == " --push"


def test_push_option_without_push() -> None:
    assert doc._push_option(push=False) == ""


####################################
#     Tests for _parse_release     #
####################################


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.2.3", ("1.2", False)),
        ("1.2", ("1.2", False)),
        ("v1.2.3", ("1.2", False)),
        ("10.20.30", ("10.20", False)),
        ("1.2.3.4", ("1.2", False)),
        ("1.2.0.post1", ("1.2", False)),
        (" 1.2.3 ", ("1.2", False)),
    ],
)
def test_parse_release_final(version: str, expected: tuple[str, bool]) -> None:
    assert _parse_release(version) == expected


@pytest.mark.parametrize(
    "version",
    ["1.2.0a1", "1.2.0b1", "1.2.0rc1", "1.2.0.dev1", "1.2.0-beta.1", "1.2.0RC1", "1.2rc1"],
)
def test_parse_release_pre_release(version: str) -> None:
    assert _parse_release(version) == ("1.2", True)


@pytest.mark.parametrize("version", ["", "1", "latest", "v", "a.b.c", "x1.2"])
def test_parse_release_invalid(version: str) -> None:
    with pytest.raises(ValueError, match=r"Cannot parse the version"):
        _parse_release(version)


###########################
#     Tests for build     #
###########################


def test_build() -> None:
    c = _context({"package": {"name": "mypkg"}})
    doc.build(c)
    assert _commands(c) == ["mkdocs build --strict --config-file docs/mkdocs.yml"]


def test_build_uses_configured_docs_config() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "mkdocs.yml"}})
    doc.build(c)
    assert _commands(c) == ["mkdocs build --strict --config-file mkdocs.yml"]


def test_build_with_args() -> None:
    c = _context({"package": {"name": "mypkg"}})
    doc.build(c, args="--site-dir out")
    assert _commands(c) == ["mkdocs build --strict --config-file docs/mkdocs.yml --site-dir out"]


def test_build_quotes_the_docs_config() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "d d/mkdocs.yml"}})
    doc.build(c)
    assert _commands(c) == ["mkdocs build --strict --config-file 'd d/mkdocs.yml'"]


###########################
#     Tests for serve     #
###########################


def test_serve() -> None:
    c = _context({"package": {"name": "mypkg"}})
    doc.serve(c)
    assert _commands(c) == ["mkdocs serve --config-file docs/mkdocs.yml"]


def test_serve_uses_configured_docs_config() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "mkdocs.yml"}})
    doc.serve(c)
    assert _commands(c) == ["mkdocs serve --config-file mkdocs.yml"]


def test_serve_with_args() -> None:
    c = _context({"package": {"name": "mypkg"}})
    doc.serve(c, args="--dev-addr 127.0.0.1:8001")
    assert _commands(c) == ["mkdocs serve --config-file docs/mkdocs.yml --dev-addr 127.0.0.1:8001"]


def test_serve_quotes_the_docs_config() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "d d/mkdocs.yml"}})
    doc.serve(c)
    assert _commands(c) == ["mkdocs serve --config-file 'd d/mkdocs.yml'"]


##################################
#     Tests for _docs_config     #
##################################


def test_docs_config_returns_the_path() -> None:
    assert _docs_config(_context({"package": {"name": "mypkg"}})) == "docs/mkdocs.yml"


def test_docs_config_missing_file_exits() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "no/such.yml"}})
    with pytest.raises(Exit, match=r"'no/such.yml' \(tasklib.paths.docs_config\) does not exist"):
        _docs_config(c)


def test_docs_config_missing_file_exit_code() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "no/such.yml"}})
    with pytest.raises(Exit) as excinfo:
        _docs_config(c)
    assert excinfo.value.code == 2


def test_docs_config_directory_is_not_a_file() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "docs"}})
    with pytest.raises(Exit, match=r"'docs' \(tasklib.paths.docs_config\) does not exist"):
        _docs_config(c)


@pytest.mark.parametrize("task", [doc.build, doc.serve, doc.publish_dev])
def test_doc_tasks_with_a_missing_config_run_nothing(task: Callable[..., None]) -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "no/such.yml"}})
    with pytest.raises(Exit, match=r"does not exist"):
        task(c)
    assert _commands(c) == []


def test_publish_latest_with_a_missing_config_runs_nothing() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "no/such.yml"}})
    with pytest.raises(Exit, match=r"does not exist"):
        doc.publish_latest(c, version="1.2")
    assert _commands(c) == []
