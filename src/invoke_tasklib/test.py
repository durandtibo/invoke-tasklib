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

COV_HELP = "Generate coverage reports (html, xml and terminal)."


def _directory_exists(c: Context, path: str, what: str) -> bool:
    r"""Check that the directory of a test scope exists.

    Pytest exits with an error when it is given a path that does not
    exist, so a project without, for example, integration tests would
    fail the task. A message is written when the directory is missing so
    that the skip is visible.

    Args:
        c: The invoke context.
        path: The directory to check.
        what: The name of the scope, used in the message, e.g.
            ``"integration tests"``.

    Returns:
        ``True`` if the directory exists, ``False`` otherwise.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.test import _directory_exists
    >>> _directory_exists(Context(config=Config()), "no/such/dir", "benchmarks")
    ⏭️  No 'no/such/dir' directory: skipping benchmarks
    False

    ```
    """
    if Path(path).is_dir():
        return True
    say(c, f"⏭️  No '{path}' directory: skipping {what}")
    return False


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
    r"""Run doctests on the Python examples of the markdown files."""
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


@task(help={"cov": COV_HELP})
def all(c: Context, cov: bool = False) -> None:  # noqa: A001 (task name, matches `inv test.all`)
    r"""Run all tests (unit, integration, and functional).

    The timeout of each test is 60 seconds, the one of the slowest scopes
    (integration and functional), because the whole ``tests`` directory
    is run in one pytest call.

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports in HTML, XML, and terminal
            formats. Default is False.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    tests = cfg["paths"]["tests"]
    say(c, "🧪 Running all tests...")
    cmd = [f"{python_executable()} -m pytest --xdoctest --timeout 60"]
    if cov:
        cmd.append(f"--cov-report html --cov-report xml --cov-report term --cov={name}")
        say(c, "📊 Coverage reports will be generated")
    cmd.append(tests)
    c.run(" ".join(cmd), pty=True)
    say(c, "✅ All tests complete")


@task(help={"cov": COV_HELP})
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


@task(help={"cov": COV_HELP})
def integration(c: Context, cov: bool = False) -> None:
    r"""Run integration tests.

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports (appended). Default is False.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    integration_tests = cfg["paths"]["integration_tests"]
    if not _directory_exists(c, integration_tests, "integration tests"):
        return
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


@task(help={"cov": COV_HELP})
def functional(c: Context, cov: bool = False) -> None:
    r"""Run functional tests.

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports (appended). Default is False.
    """
    cfg = get_config(c)
    name = cfg["package"]["name"]
    functional_tests = cfg["paths"]["functional_tests"]
    if not _directory_exists(c, functional_tests, "functional tests"):
        return
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


@task(help={"open_browser": "Open the HTML report in the default web browser."})
def coverage_report(c: Context, open_browser: bool = False) -> None:
    r"""Generate an HTML coverage report.

    The report is built from the last recorded coverage data, and the
    terminal summary is printed.

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
    if not _directory_exists(c, benchmarks, "benchmarks"):
        return
    say(c, "⏱️  Running benchmarks...")
    c.run(f"{python_executable()} -m pytest {benchmarks}/ --benchmark-only", pty=True)
    say(c, "✅ Benchmarks complete")
