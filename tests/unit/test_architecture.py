from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from invoke_tasklib import check, fix
from invoke_tasklib._graph import import_graph, read_sources
from invoke_tasklib._steps import step_modules, step_programs
from invoke_tasklib.config import load_config
from invoke_tasklib.tools import TOOLS
from tests.helpers import make_context

if TYPE_CHECKING:
    from collections.abc import Callable

SRC = Path(__file__).parents[2] / "src" / "invoke_tasklib"
PACKAGE = "invoke_tasklib"

# The layers of ``architecture.md``: a module imports only from its own
# layer or from the ones below it, and not from its own layer in the
# layers of ``_FLAT_LAYERS`` (the task modules and the composites).
LAYERS = {
    "_discover": 0,
    "config": 1,
    "runner": 1,
    "tools": 1,
    "output": 1,
    "_steps": 2,
    "_files": 2,
    "_graph": 2,
    "formatting": 3,
    "lint": 3,
    "typecheck": 3,
    "testing": 3,
    "env": 3,
    "release": 3,
    "doc": 3,
    "security": 3,
    "imports": 3,
    "clean": 3,
    "show": 3,
    "check": 4,
    "fix": 4,
    "__init__": 5,
}
_FLAT_LAYERS = {3, 4}

# The edges that break the layers today, each removed by a step of
# ``review/target_state.md``.
KNOWN_VIOLATIONS = {"clean -> testing"}

# ``config.show`` prints the raw Invoke config, which is its job.
RAW_CONFIG_MODULES = {"show.py"}


def _source_files() -> list[Path]:
    r"""List the Python files of the package, sorted."""
    return sorted(SRC.rglob("*.py"))


def _is_under(path: Path, *names: str) -> bool:
    r"""Tell if ``path`` is one of ``names`` or inside the folders."""
    relative = path.relative_to(SRC).as_posix()
    return any(relative == name or relative.startswith(f"{name}/") for name in names)


def _locations(allowed: tuple[str, ...], test: Callable[[ast.expr], bool]) -> list[str]:
    r"""Find the expressions of the package that satisfy ``test``.

    Args:
        allowed: The files or folders (relative to the package) that
            are not scanned.
        test: A function that tells if an expression is a violation.

    Returns:
        One ``file:line`` string per violation.
    """
    found = []
    for path in _source_files():
        if _is_under(path, *allowed):
            continue
        name = path.relative_to(SRC).as_posix()
        nodes = ast.walk(ast.parse(path.read_text()))
        found.extend(f"{name}:{n.lineno}" for n in nodes if isinstance(n, ast.expr) and test(n))
    return found


def _is_c_run(node: ast.expr) -> bool:
    r"""Tell if a call is ``c.run(...)``."""
    func = node.func if isinstance(node, ast.Call) else None
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "run"
        and isinstance(func.value, ast.Name)
        and func.value.id == "c"
    )


def _is_print(node: ast.expr) -> bool:
    r"""Tell if a call is ``print(...)``."""
    return (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"
    )


def _is_c_config(node: ast.expr) -> bool:
    r"""Tell if an attribute is ``c.config``."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "config"
        and isinstance(node.value, ast.Name)
        and node.value.id == "c"
    )


def _group(module: str) -> str:
    r"""Map a dotted module name to its name in ``LAYERS``."""
    parts = module.split(".")
    return "__init__" if len(parts) == 1 else parts[1]


def _layer_violations() -> set[str]:
    r"""List the imports of the package that break the layers."""
    sources, packages = read_sources(PACKAGE)
    graph = import_graph(sources, packages, lazy=True)
    found = set()
    for module, targets in graph.items():
        source = _group(module)
        for target in (_group(t) for t in targets):
            if source == target:
                continue
            lower, higher = LAYERS[target], LAYERS[source]
            if lower > higher or (lower == higher and higher in _FLAT_LAYERS):
                found.add(f"{source} -> {target}")
    return found


def _tools_needed(steps: dict) -> set[str]:
    r"""List the programs and modules named by a dict of steps."""
    cfg = load_config(make_context({"package": {"name": "mypkg"}}))
    names: set[str] = set()
    for step in steps.values():
        names.update(step_programs(step, cfg), step_modules(step, cfg))
    return names


##########################################
#     Tests for P1 (one entry point)     #
##########################################


def test_no_task_calls_c_run_outside_the_runner() -> None:
    assert _locations(("runner.py",), _is_c_run) == []


def test_no_module_calls_print_outside_the_output_module() -> None:
    assert _locations(("output.py",), _is_print) == []


def test_no_task_reads_c_config_directly() -> None:
    found = _locations(("runner.py", "output.py", "config", *RAW_CONFIG_MODULES), _is_c_config)
    assert found == []


#####################################
#     Tests for M1 (the layers)     #
#####################################


def test_every_module_of_the_package_has_a_layer() -> None:
    sources, _ = read_sources(PACKAGE)
    assert {_group(m) for m in sources} - {"__main__"} - set(LAYERS) == set()


def test_imports_follow_the_layers() -> None:
    assert _layer_violations() - KNOWN_VIOLATIONS == set()


@pytest.mark.parametrize("edge", sorted(KNOWN_VIOLATIONS))
def test_known_violations_still_exist(edge: str) -> None:
    # When a step removes a violation, remove it from KNOWN_VIOLATIONS.
    assert edge in _layer_violations()


#####################################
#     Tests for the tool tables     #
#####################################


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_tool_is_registered_under_its_name(name: str) -> None:
    assert TOOLS[name].name == name


@pytest.mark.parametrize("steps", [check.STEPS, fix.STEPS], ids=["check", "fix"])
def test_every_tool_of_the_steps_is_in_tools(steps: dict) -> None:
    assert _tools_needed(steps) - set(TOOLS) == set()
