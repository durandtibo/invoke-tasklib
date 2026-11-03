r"""Test and benchmark tasks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import EXCLUDED_DIRS, get_config
from invoke_tasklib.output import say
from invoke_tasklib.runner import python_executable

if TYPE_CHECKING:
    from invoke.context import Context


@task
def doctest_src(c: Context) -> None:
    r"""Run doctests on source code."""
    cfg = get_config(c)
    src = cfg["paths"]["src"]
    say(c, "📚 Running doctests on source code...")
    c.run(f"{python_executable()} -m pytest --xdoctest {src}", pty=True)
    say(c, "✅ Doctest validation complete")


@task
def doctest_markdown(c: Context) -> None:
    r"""Run doctests on Python code examples embedded in markdown
    files."""
    md_files = sorted(p for p in Path().rglob("*.md") if not EXCLUDED_DIRS.intersection(p.parts))
    say(c, f"📚 Found {len(md_files)} markdown files")
    for f in md_files:
        say(c, f"🔍 Checking: {f}")
        c.run(
            f"{python_executable()} -m doctest -o NORMALIZE_WHITESPACE -o ELLIPSIS -o REPORT_NDIFF {f}",
            pty=True,
        )
    say(c, f"✅ All {len(md_files)} markdown files have been checked")


@task
def doctest(c: Context) -> None:
    r"""Run doctests on both source code and markdown files."""
    doctest_src(c)
    doctest_markdown(c)


@task
def all(c: Context, cov: bool = False) -> None:  # noqa: A001 (task name, matches `inv test.all`)
    r"""Run all tests (unit, integration, and functional).

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports in HTML, XML, and terminal
            formats. Default is False.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    tests = cfg["paths"]["tests"]
    say(c, "🧪 Running all tests...")
    cmd = [f"{python_executable()} -m pytest --xdoctest --timeout 10"]
    if cov:
        cmd.append(f"--cov-report html --cov-report xml --cov-report term --cov={name}")
        say(c, "📊 Coverage reports will be generated")
    cmd.append(tests)
    c.run(" ".join(cmd), pty=True)
    say(c, "✅ All tests complete")


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
    say(c, "🧪 Running unit tests...")
    cmd = [f"{python_executable()} -m pytest --xdoctest --timeout 10"]
    if cov:
        cmd.append(f"--cov-report html --cov-report xml --cov-report term --cov={name}")
        say(c, "📊 Coverage reports will be generated")
    cmd.append(unit_tests)
    c.run(" ".join(cmd), pty=True)
    say(c, "✅ Unit tests complete")


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
    say(c, "🧪 Running integration tests...")
    cmd = [f"{python_executable()} -m pytest --xdoctest --timeout 60"]
    if cov:
        cmd.append(
            f"--cov-report html --cov-report xml --cov-report term --cov-append --cov={name}"
        )
        say(c, "📊 Coverage reports will be generated (appending)")
    cmd.append(integration_tests)
    c.run(" ".join(cmd), pty=True)
    say(c, "✅ Integration tests complete")


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
    say(c, "🧪 Running functional tests...")
    cmd = [f"{python_executable()} -m pytest --xdoctest --timeout 60"]
    if cov:
        cmd.append(
            f"--cov-report html --cov-report xml --cov-report term --cov-append --cov={name}"
        )
        say(c, "📊 Coverage reports will be generated (appending)")
    cmd.append(functional_tests)
    c.run(" ".join(cmd), pty=True)
    say(c, "✅ Functional tests complete")


@task
def coverage_report(c: Context, open_browser: bool = False) -> None:
    r"""Generate an HTML coverage report from the last recorded coverage
    data and print the terminal summary.

    Args:
        c: The invoke context.
        open_browser: If True, open the generated HTML report in the
            default web browser. Default is False.
    """
    say(c, "📊 Generating coverage report...")
    c.run("coverage html", pty=True)
    c.run("coverage report", pty=True)
    if open_browser:
        say(c, "🌐 Opening coverage report in the browser...")
        c.run(f"{python_executable()} -m webbrowser -t htmlcov/index.html")
    say(c, "✅ Coverage report generated in htmlcov/")


@task
def benchmark(c: Context) -> None:
    r"""Run performance benchmarks."""
    cfg = get_config(c)
    benchmarks = cfg["paths"]["benchmarks"]
    say(c, "⏱️  Running benchmarks...")
    c.run(f"{python_executable()} -m pytest {benchmarks}/ --benchmark-only", pty=True)
    say(c, "✅ Benchmarks complete")
