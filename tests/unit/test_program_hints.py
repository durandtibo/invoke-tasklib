from __future__ import annotations

import contextlib
import shlex
from typing import TYPE_CHECKING

import pytest
from invoke.exceptions import Exit

from invoke_tasklib import make_ns
from invoke_tasklib.runner import (
    PROGRAM_GROUPS,
    PROGRAM_HINTS,
    UNCHECKED_PROGRAMS,
    _strip_assignments,
)
from tests.helpers import commands, make_context

if TYPE_CHECKING:
    from pathlib import Path

    from invoke.tasks import Task

_NS = make_ns()
_TASKS = {
    f"{namespace}.{name}": task
    for namespace, sub in _NS.collections.items()
    for name, task in sub.tasks.items()
}


@pytest.fixture(autouse=True)
def _project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Run in a project that has the directories the tasks look for."""
    for name in ("src", "tests", "docs"):
        (tmp_path / name).mkdir()
    (tmp_path / "mkdocs.yml").write_text("site_name: x\n")
    monkeypatch.chdir(tmp_path)


def _programs_of(task: Task) -> set[str]:
    r"""Return the programs that a task looks up on the ``PATH``.

    The task runs on a ``MockContext`` and a task that exits (for
    example ``release.publish`` on an untagged ``HEAD``) is kept with
    the commands it ran before.

    Args:
        task: The task to run.

    Returns:
        The program of each recorded command, without the programs
        given by a path.
    """
    c = make_context({"package": {"name": "mypkg"}})
    with contextlib.suppress(Exit):
        task(c)
    words = (_strip_assignments(shlex.split(command)) for command in commands(c))
    programs = {w[0] for w in words if w}
    return {p for p in programs if "/" not in p}


###############################################
#     Tests for the hints of the programs     #
###############################################


@pytest.mark.parametrize("name", sorted(_TASKS))
def test_every_program_of_a_task_has_an_install_hint(name: str) -> None:
    known = set(PROGRAM_HINTS) | set(PROGRAM_GROUPS) | UNCHECKED_PROGRAMS
    assert _programs_of(_TASKS[name]) - known == set()
