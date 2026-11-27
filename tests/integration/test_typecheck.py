from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src"
TYPED = 'def one() -> int:\n    r"""Return 1."""\n    return 1\n'
UNTYPED = 'def one(x):\n    r"""Return x."""\n    return x\n'


def _check_public_api(project: Path) -> subprocess.CompletedProcess[str]:
    r"""Run ``types.check-public-api`` in ``project``.

    The virtual environment is not activated: its directory is not on
    the ``PATH``. ``PYTHONPATH`` makes the packages of ``site``
    importable, like installed ones.
    """
    bin_dir = Path(sys.executable).parent
    path = [d for d in os.environ["PATH"].split(os.pathsep) if Path(d) != bin_dir]
    pythonpath = os.pathsep.join([str(SRC), str(project / "site")])
    env = {**os.environ, "PYTHONPATH": pythonpath, "PATH": os.pathsep.join(path)}
    env.pop("VIRTUAL_ENV", None)
    return subprocess.run(
        [sys.executable, "-m", "invoke", "types.check-public-api"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    r"""Create a project with a typed package ``demo`` in ``site``."""
    (tmp_path / "tasks.py").write_text("from invoke_tasklib import make_ns\n\nns = make_ns()\n")
    (tmp_path / "invoke.yaml").write_text("tasklib:\n  package:\n    name: demo\n")
    package = tmp_path / "site" / "demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(TYPED)
    (package / "py.typed").touch()
    return tmp_path


############################################
#     Tests for types.check-public-api     #
############################################


def test_check_public_api_passes_on_a_typed_package(project: Path) -> None:
    assert _check_public_api(project).returncode == 0


def test_check_public_api_fails_on_an_untyped_function(project: Path) -> None:
    (project / "site" / "demo" / "__init__.py").write_text(UNTYPED)
    assert _check_public_api(project).returncode == 1


def test_check_public_api_fails_without_py_typed(project: Path) -> None:
    (project / "site" / "demo" / "py.typed").unlink()
    assert "No py.typed file found" in _check_public_api(project).stdout


def test_check_public_api_finds_an_installed_package(project: Path) -> None:
    (project / "invoke.yaml").write_text("tasklib:\n  package:\n    name: invoke_tasklib\n")
    assert 'Symbols exported by "invoke_tasklib"' in _check_public_api(project).stdout
