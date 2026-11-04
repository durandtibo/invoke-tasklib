from __future__ import annotations

import stat
from typing import TYPE_CHECKING

import pytest
from invoke.config import Config

from invoke_tasklib import security
from tests.integration.test_imports import _SubprocessContext

if TYPE_CHECKING:
    from pathlib import Path

_UV = """#!/bin/sh
# fake `uv export ... -o FILE`: write the file named after -o
while [ "$1" != "-o" ]; do shift; done
echo "demo==1.0" > "$2"
"""

_UVX = """#!/bin/sh
# fake `uvx --from SPEC pip-audit -r FILE ...`: record the content of FILE
cat "$5" > "$FAKE_AUDIT_LOG"
"""


@pytest.fixture
def fake_uv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, script in (("uv", _UV), ("uvx", _UVX)):
        path = bin_dir / name
        path.write_text(script)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "audit.log"
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    monkeypatch.setenv("FAKE_AUDIT_LOG", str(log))
    return log


def test_audit_gives_the_exported_requirements_to_the_audit(fake_uv: Path) -> None:
    security.audit(_SubprocessContext(config=Config()))
    assert fake_uv.read_text() == "demo==1.0\n"
