from __future__ import annotations

from unittest.mock import Mock, patch

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import security


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]


###########################
#     Tests for audit     #
###########################


def _audit_commands() -> list[str]:
    c = _context()
    with patch("tempfile.TemporaryDirectory") as tmp:
        tmp.return_value.__enter__.return_value = "/work/x"
        security.audit(c)
    return _commands(c)


def test_audit_commands() -> None:
    assert _audit_commands() == [
        (
            "uv export --locked --no-emit-project --no-hashes --all-groups "
            "--quiet -o /work/x/requirements.txt"
        ),
        "uvx pip-audit -r /work/x/requirements.txt --no-deps --disable-pip",
    ]


def test_audit_with_args() -> None:
    c = _context()
    with patch("tempfile.TemporaryDirectory") as tmp:
        tmp.return_value.__enter__.return_value = "/work/x"
        security.audit(c, args="--ignore-vuln PYSEC-1")
    assert _commands(c)[1] == (
        "uvx pip-audit -r /work/x/requirements.txt --no-deps --disable-pip --ignore-vuln PYSEC-1"
    )


def test_audit_does_not_sync_the_environment() -> None:
    assert not any(cmd.startswith("uv run") for cmd in _audit_commands())


def test_audit_quotes_the_requirements_path() -> None:
    c = _context()
    with patch("tempfile.TemporaryDirectory") as tmp:
        tmp.return_value.__enter__.return_value = "/work/a b"
        security.audit(c)
    assert "'/work/a b/requirements.txt'" in _commands(c)[1]
