from __future__ import annotations

import sys
import types

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import doc


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    return [call.args[0] for call in c.run.call_args_list]


def test_publish_dev() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "docs/mkdocs.yml"}})
    doc.publish_dev(c)
    commands = _commands(c)
    assert "mike delete --config-file docs/mkdocs.yml main" in commands
    assert "mike deploy --config-file docs/mkdocs.yml --push --update-aliases main dev" in commands


def _install_fake_feu_module(monkeypatch, version: str | None) -> None:
    def _get_last_version_tag_name() -> str:
        if version is None:
            msg = "no tags found"
            raise RuntimeError(msg)
        return version

    fake_local_git = types.ModuleType("feu.local_git")
    fake_local_git.get_last_version_tag_name = _get_last_version_tag_name
    fake_feu = types.ModuleType("feu")
    fake_feu.local_git = fake_local_git
    monkeypatch.setitem(sys.modules, "feu", fake_feu)
    monkeypatch.setitem(sys.modules, "feu.local_git", fake_local_git)


def test_publish_latest_uses_last_version_tag(monkeypatch) -> None:
    _install_fake_feu_module(monkeypatch, "1.2.3")
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "docs/mkdocs.yml"}})
    doc.publish_latest(c)
    commands = _commands(c)
    assert "mike delete --config-file docs/mkdocs.yml 1.2" in commands
    assert (
        "mike deploy --config-file docs/mkdocs.yml --push --update-aliases 1.2 latest" in commands
    )
    assert "mike set-default --config-file docs/mkdocs.yml --push --allow-empty latest" in commands


def test_publish_latest_falls_back_when_no_tag(monkeypatch) -> None:
    _install_fake_feu_module(monkeypatch, None)
    c = _context({"package": {"name": "mypkg"}, "paths": {"docs_config": "docs/mkdocs.yml"}})
    doc.publish_latest(c)
    commands = _commands(c)
    assert "mike delete --config-file docs/mkdocs.yml 0.0" in commands
    assert (
        "mike deploy --config-file docs/mkdocs.yml --push --update-aliases 0.0 latest" in commands
    )
