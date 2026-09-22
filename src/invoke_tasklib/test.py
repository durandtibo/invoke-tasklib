r"""Test and benchmark tasks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import get_config

if TYPE_CHECKING:
    from invoke.context import Context

logger: logging.Logger = logging.getLogger(__name__)

MARKDOWN_DOCTEST_EXCLUDE_DIRS = frozenset({".venv", ".pytest_cache", ".git", "node_modules"})


@task
def doctest_src(c: Context) -> None:
    r"""Run doctests on source code."""
    cfg = get_config(c)
    src = cfg["paths"]["src"]
    logger.info("📚 Running doctests on source code...")
    c.run(f"python -m pytest --xdoctest {src}", pty=True)
    logger.info("✅ Doctest validation complete")


@task
def doctest_markdown(c: Context) -> None:
    r"""Run doctests on Python code examples embedded in markdown files."""
    md_files = sorted(
        p for p in Path().rglob("*.md") if not MARKDOWN_DOCTEST_EXCLUDE_DIRS.intersection(p.parts)
    )
    logger.info(f"📚 Found {len(md_files)} markdown files")
    for f in md_files:
        logger.info(f"🔍 Checking: {f}")
        c.run(
            f"python -m doctest -o NORMALIZE_WHITESPACE -o ELLIPSIS -o REPORT_NDIFF {f}", pty=True
        )
    logger.info(f"✅ All {len(md_files)} markdown files have been checked")


@task
def doctest(c: Context) -> None:
    r"""Run doctests on both source code and markdown files."""
    doctest_src(c)
    doctest_markdown(c)


@task
def all(c: Context, cov: bool = False) -> None:
    r"""Run all tests (unit, integration, and functional).

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports in HTML, XML, and terminal
            formats. Default is False.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    tests = cfg["paths"]["tests"]
    logger.info("🧪 Running all tests...")
    cmd = ["python -m pytest --xdoctest --timeout 10"]
    if cov:
        cmd.append(f"--cov-report html --cov-report xml --cov-report term --cov={name}")
        logger.info("📊 Coverage reports will be generated")
    cmd.append(tests)
    c.run(" ".join(cmd), pty=True)
    logger.info("✅ All tests complete")


@task
def unit(c: Context, cov: bool = False) -> None:
    r"""Run unit tests.

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports. Default is False.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    unit_tests = cfg["paths"]["unit_tests"]
    logger.info("🧪 Running unit tests...")
    cmd = ["python -m pytest --xdoctest --timeout 10"]
    if cov:
        cmd.append(f"--cov-report html --cov-report xml --cov-report term --cov={name}")
        logger.info("📊 Coverage reports will be generated")
    cmd.append(unit_tests)
    c.run(" ".join(cmd), pty=True)
    logger.info("✅ Unit tests complete")


@task
def integration(c: Context, cov: bool = False) -> None:
    r"""Run integration tests.

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports (appended). Default is False.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    integration_tests = cfg["paths"]["integration_tests"]
    logger.info("🧪 Running integration tests...")
    cmd = ["python -m pytest --xdoctest --timeout 60"]
    if cov:
        cmd.append(
            f"--cov-report html --cov-report xml --cov-report term --cov-append --cov={name}"
        )
        logger.info("📊 Coverage reports will be generated (appending)")
    cmd.append(integration_tests)
    c.run(" ".join(cmd), pty=True)
    logger.info("✅ Integration tests complete")


@task
def functional(c: Context, cov: bool = False) -> None:
    r"""Run functional tests.

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports (appended). Default is False.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    functional_tests = cfg["paths"]["functional_tests"]
    logger.info("🧪 Running functional tests...")
    cmd = ["python -m pytest --xdoctest --timeout 60"]
    if cov:
        cmd.append(
            f"--cov-report html --cov-report xml --cov-report term --cov-append --cov={name}"
        )
        logger.info("📊 Coverage reports will be generated (appending)")
    cmd.append(functional_tests)
    c.run(" ".join(cmd), pty=True)
    logger.info("✅ Functional tests complete")


@task
def benchmark(c: Context) -> None:
    r"""Run performance benchmarks."""
    cfg = get_config(c)
    benchmarks = cfg["paths"]["benchmarks"]
    logger.info("⏱️  Running benchmarks...")
    c.run(f"python -m pytest {benchmarks}/ --benchmark-only", pty=True)
    logger.info("✅ Benchmarks complete")
