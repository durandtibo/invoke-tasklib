from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _all_programs_available(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Make the unit tests independent of the tools installed on the
    machine: every program is found on the ``PATH``."""
    monkeypatch.setattr(
        "invoke_tasklib.tools.shutil.which", lambda program, **_kwargs: f"/bin/{program}"
    )
