from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.exceptions import Exit

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

from invoke_tasklib import doc
from invoke_tasklib.doc import _parse_release


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
        "mike delete --config-file docs/mkdocs.yml main",
        "mike deploy --config-file docs/mkdocs.yml --push --update-aliases main dev",
    ]


def _install_fake_feu_module(monkeypatch: MonkeyPatch, version: str | None) -> None:
    def _get_last_version_tag_name() -> str:
        if version is None:
            msg = "no tags found"
            raise RuntimeError(msg)
        return version

    fake_local_git = types.ModuleType("feu.local_git")
    monkeypatch.setattr(
        fake_local_git, "get_last_version_tag_name", _get_last_version_tag_name, raising=False
    )
    fake_feu = types.ModuleType("feu")
    monkeypatch.setattr(fake_feu, "local_git", fake_local_git, raising=False)
    monkeypatch.setitem(sys.modules, "feu", fake_feu)
    monkeypatch.setitem(sys.modules, "feu.local_git", fake_local_git)


####################################
#     Tests for publish_latest     #
####################################

_DOCS = {"package": {"name": "mypkg"}, "paths": {"docs_config": "docs/mkdocs.yml"}}
_DEPLOY_1_2 = [
    "mike deploy --config-file docs/mkdocs.yml --push --update-aliases 1.2 latest",
    "mike set-default --config-file docs/mkdocs.yml --push --allow-empty latest",
]


def test_publish_latest_uses_last_version_tag(monkeypatch: MonkeyPatch) -> None:
    _install_fake_feu_module(monkeypatch, "1.2.3")
    c = _context(_DOCS)
    doc.publish_latest(c)
    assert _commands(c) == _DEPLOY_1_2


def test_publish_latest_does_not_delete_the_version_first(monkeypatch: MonkeyPatch) -> None:
    _install_fake_feu_module(monkeypatch, "1.2.3")
    c = _context(_DOCS)
    doc.publish_latest(c)
    assert not any(cmd.startswith("mike delete") for cmd in _commands(c))


def test_publish_latest_fails_when_no_tag(monkeypatch: MonkeyPatch) -> None:
    _install_fake_feu_module(monkeypatch, None)
    c = _context(_DOCS)
    with pytest.raises(Exit, match=r"No version tag found"):
        doc.publish_latest(c)


def test_publish_latest_does_not_publish_when_no_tag(monkeypatch: MonkeyPatch) -> None:
    _install_fake_feu_module(monkeypatch, None)
    c = _context(_DOCS)
    with pytest.raises(Exit, match=r"No version tag found"):
        doc.publish_latest(c)
    assert _commands(c) == []


@pytest.mark.parametrize("tag", ["1.2.0rc1", "1.2.0a1", "1.2.0b2", "1.2.0.dev3"])
def test_publish_latest_skips_pre_release_tag(monkeypatch: MonkeyPatch, tag: str) -> None:
    _install_fake_feu_module(monkeypatch, tag)
    c = _context(_DOCS)
    doc.publish_latest(c)
    assert _commands(c) == []


def test_publish_latest_reports_skipped_pre_release(
    monkeypatch: MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_fake_feu_module(monkeypatch, "1.2.0rc1")
    doc.publish_latest(_context(_DOCS))
    assert capsys.readouterr().out == (
        "⏭️  Skipping the pre-release version 1.2.0rc1: latest docs not published\n"
    )


def test_publish_latest_with_explicit_version_does_not_need_feu(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "feu", None)
    monkeypatch.setitem(sys.modules, "feu.local_git", None)
    c = _context(_DOCS)
    doc.publish_latest(c, version="1.2.3")
    assert _commands(c) == _DEPLOY_1_2


def test_publish_latest_explicit_version_wins_over_tag(monkeypatch: MonkeyPatch) -> None:
    _install_fake_feu_module(monkeypatch, "3.0.0")
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
