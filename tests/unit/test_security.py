from __future__ import annotations

from unittest.mock import patch

from invoke_tasklib import security
from tests.helpers import commands, make_context

###########################
#     Tests for audit     #
###########################


def _audit_commands() -> list[str]:
    c = make_context()
    with patch("tempfile.TemporaryDirectory") as tmp:
        tmp.return_value.__enter__.return_value = "/work/x"
        security.audit(c)
    return commands(c)


def test_audit_commands() -> None:
    assert _audit_commands() == [
        (
            "uv export --locked --no-emit-project --no-hashes --all-groups "
            "--quiet -o /work/x/requirements.txt"
        ),
        (
            "uvx --from 'pip-audit>=2.10,<3' pip-audit -r /work/x/requirements.txt "
            "--no-deps --disable-pip"
        ),
    ]


def test_audit_with_args() -> None:
    c = make_context()
    with patch("tempfile.TemporaryDirectory") as tmp:
        tmp.return_value.__enter__.return_value = "/work/x"
        security.audit(c, args="--ignore-vuln PYSEC-1")
    assert commands(c)[1] == (
        "uvx --from 'pip-audit>=2.10,<3' pip-audit -r /work/x/requirements.txt "
        "--no-deps --disable-pip --ignore-vuln PYSEC-1"
    )


def test_audit_does_not_sync_the_environment() -> None:
    assert not any(cmd.startswith("uv run") for cmd in _audit_commands())


def test_audit_quotes_the_requirements_path() -> None:
    c = make_context()
    with patch("tempfile.TemporaryDirectory") as tmp:
        tmp.return_value.__enter__.return_value = "/work/a b"
        security.audit(c)
    assert "'/work/a b/requirements.txt'" in commands(c)[1]
