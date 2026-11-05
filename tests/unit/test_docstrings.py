from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src" / "invoke_tasklib"


def _missing_docstrings(source: str) -> list[str]:
    r"""Return the functions and classes of a module without docstring.

    The private ones are included, which ruff does not report. The
    stubs decorated with ``overload`` are not (ruff forbids a docstring
    on them: the implementation has it).

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
        and not _is_overload(node)
    ]


def _is_overload(node: ast.AST) -> bool:
    r"""Tell whether a function is decorated with ``overload``.

    Args:
        node: A node of the syntax tree.

    Returns:
        True for a function decorated with ``overload`` or
        ``typing.overload``.
    """
    decorators = getattr(node, "decorator_list", [])
    names = {d.id if isinstance(d, ast.Name) else getattr(d, "attr", "") for d in decorators}
    return "overload" in names


######################################
#     Tests for the source files     #
######################################


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: str(p.relative_to(SRC)))
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


def test_missing_docstrings_ignores_an_overload_stub() -> None:
    assert _missing_docstrings("@overload\ndef f(x: int) -> int: ...") == []


def test_missing_docstrings_ignores_a_typing_overload_stub() -> None:
    assert _missing_docstrings("@typing.overload\ndef f(x: int) -> int: ...") == []


def test_missing_docstrings_reports_a_function_with_another_decorator() -> None:
    assert _missing_docstrings("@task\ndef f(x: int) -> int: ...") == ["f"]
