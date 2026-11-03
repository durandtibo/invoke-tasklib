from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src" / "invoke_tasklib"


def _missing_docstrings(source: str) -> list[str]:
    r"""Return the functions and classes of a module without docstring.

    The private ones are included, which ruff does not report.

    Args:
        source: The source code of a module.

    Returns:
        The names of the nodes without docstring.
    """
    tree = ast.parse(source)
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and ast.get_docstring(node) is None
    ]


######################################
#     Tests for the source files     #
######################################


@pytest.mark.parametrize("path", sorted(SRC.glob("*.py")), ids=lambda p: p.name)
def test_every_function_of_src_has_a_docstring(path: Path) -> None:
    assert _missing_docstrings(path.read_text()) == []


#########################################
#     Tests for _missing_docstrings     #
#########################################


def test_missing_docstrings_accepts_a_documented_function() -> None:
    assert _missing_docstrings('def f():\n    """Doc."""\n') == []


def test_missing_docstrings_reports_a_public_function() -> None:
    assert _missing_docstrings("def f():\n    pass\n") == ["f"]


def test_missing_docstrings_reports_a_private_function() -> None:
    assert _missing_docstrings("def _f():\n    pass\n") == ["_f"]


def test_missing_docstrings_reports_an_async_function() -> None:
    assert _missing_docstrings("async def f():\n    pass\n") == ["f"]


def test_missing_docstrings_reports_a_class() -> None:
    assert _missing_docstrings("class C:\n    pass\n") == ["C"]


def test_missing_docstrings_reports_a_method() -> None:
    assert _missing_docstrings('class C:\n    """Doc."""\n\n    def m(self):\n        pass\n') == [
        "m"
    ]


def test_missing_docstrings_reports_a_nested_function() -> None:
    assert _missing_docstrings('def f():\n    """Doc."""\n\n    def g():\n        pass\n') == ["g"]


def test_missing_docstrings_ignores_a_module_without_function() -> None:
    assert _missing_docstrings("x = 1\n") == []
