from __future__ import annotations

from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import test as test_tasks


def _context(tasklib_config: dict | None = None) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=True)


def _commands(c: MockContext) -> list[str]:
    return [call.args[0] for call in c.run.call_args_list]


def test_doctest() -> None:
    c = _context({"package": {"name": "mypkg"}, "paths": {"src": "src/mypkg"}})
    test_tasks.doctest(c)
    assert _commands(c) == ["python -m pytest --xdoctest src/mypkg"]


def test_all_without_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.all(c)
    assert _commands(c) == ["python -m pytest --xdoctest --timeout 10 tests"]


def test_all_with_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.all(c, cov=True)
    assert _commands(c) == [
        "python -m pytest --xdoctest --timeout 10 "
        "--cov-report html --cov-report xml --cov-report term --cov=mypkg tests"
    ]


def test_unit_without_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c)
    assert _commands(c) == ["python -m pytest --xdoctest --timeout 10 tests/unit"]


def test_unit_with_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.unit(c, cov=True)
    assert _commands(c) == [
        "python -m pytest --xdoctest --timeout 10 "
        "--cov-report html --cov-report xml --cov-report term --cov=mypkg tests/unit"
    ]


def test_integration_without_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.integration(c)
    assert _commands(c) == ["python -m pytest --xdoctest --timeout 60 tests/integration"]


def test_integration_with_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.integration(c, cov=True)
    assert _commands(c) == [
        "python -m pytest --xdoctest --timeout 60 --cov-report html --cov-report xml "
        "--cov-report term --cov-append --cov=mypkg tests/integration"
    ]


def test_functional_without_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.functional(c)
    assert _commands(c) == ["python -m pytest --xdoctest --timeout 60 tests/functional"]


def test_functional_with_coverage() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.functional(c, cov=True)
    assert _commands(c) == [
        "python -m pytest --xdoctest --timeout 60 --cov-report html --cov-report xml "
        "--cov-report term --cov-append --cov=mypkg tests/functional"
    ]


def test_benchmark() -> None:
    c = _context({"package": {"name": "mypkg"}})
    test_tasks.benchmark(c)
    assert _commands(c) == ["python -m pytest tests/benchmarks/ --benchmark-only"]
