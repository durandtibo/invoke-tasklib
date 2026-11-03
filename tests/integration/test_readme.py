from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

README = Path(__file__).parents[2] / "README.md"
PYTHON_BLOCKS = re.findall(r"```python\n(.*?)```", README.read_text(), flags=re.DOTALL)


@pytest.mark.parametrize("block", PYTHON_BLOCKS, ids=range(len(PYTHON_BLOCKS)))
def test_readme_python_block_is_a_valid_tasks_file(block: str, tmp_path: Path) -> None:
    (tmp_path / "tasks.py").write_text(block)
    proc = subprocess.run(
        [sys.executable, "-m", "invoke", "--list"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_readme_has_python_blocks() -> None:
    assert len(PYTHON_BLOCKS) == 3
