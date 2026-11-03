r"""Test and benchmark tasks."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import EXCLUDED_DIRS, load_config
from invoke_tasklib.output import say
from invoke_tasklib.runner import ARGS_HELP, PATHS_HELP, build_command, python_executable, run

if TYPE_CHECKING:
    from invoke.context import Context

COV_HELP = "Generate coverage reports (the formats of tasklib.test.cov_reports)."
_DOCTEST_OPTIONS = "-o NORMALIZE_WHITESPACE -o ELLIPSIS -o REPORT_NDIFF"
MARKDOWN_EXCLUDED_DIRS: frozenset[str] = EXCLUDED_DIRS | {
    "build",
    "dist",
    "site",
    "htmlcov",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".ruff_cache",
}
r"""Directories whose markdown files are never checked."""
PYTEST_HELP = {"cov": COV_HELP, "args": ARGS_HELP, "paths": PATHS_HELP}


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
    >>> from invoke_tasklib.testing import _directory_exists
    >>> _ = _directory_exists(Context(config=Config()), "no/such/dir", "benchmarks")
    ⏭️  No 'no/such/dir' directory: skipping benchmarks

    ```
    """
    if Path(path).is_dir():
        return True
    say(c, f"⏭️  No '{path}' directory: skipping {what}")
    return False


@task
def doctest_src(c: Context) -> None:
    r"""Run doctests on source code."""
    cfg = load_config(c)
    src = cfg.paths.src
    say(c, "📚 Running doctests on source code...")
    run(c, f"{python_executable()} -m pytest --xdoctest {shlex.quote(src)}")
    say(c, "✅ Doctest validation complete")


def _find_markdown_files(root: Path) -> list[Path]:
    r"""Find the markdown files under a root directory.

    The directories in ``MARKDOWN_EXCLUDED_DIRS`` (``.venv``, ``.git``,
    ``site``, ...) are not walked into, so a virtual environment or a
    build directory is never traversed.

    Args:
        root: The directory to search.

    Returns:
        The sorted paths of the ``.md`` files found.

    Example usage:

    ```pycon
    >>> import tempfile
    >>> from pathlib import Path
    >>> from invoke_tasklib.testing import _find_markdown_files
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     (Path(tmp) / "docs").mkdir()
    ...     (Path(tmp) / ".venv").mkdir()
    ...     _ = (Path(tmp) / "docs" / "a.md").write_text("")
    ...     _ = (Path(tmp) / ".venv" / "b.md").write_text("")
    ...     [p.relative_to(tmp).as_posix() for p in _find_markdown_files(Path(tmp))]
    ...
    ['docs/a.md']

    ```
    """
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in MARKDOWN_EXCLUDED_DIRS]
        found.extend(Path(dirpath) / name for name in filenames if name.endswith(".md"))
    return sorted(found)


@task
def doctest_markdown(c: Context) -> None:
    r"""Run doctests on the Python examples of the markdown files."""
    md_files = _find_markdown_files(Path())
    say(c, f"📚 Found {len(md_files)} markdown files")
    if md_files:
        files = " ".join(shlex.quote(str(f)) for f in md_files)
        run(c, f"{python_executable()} -m doctest {_DOCTEST_OPTIONS} {files}")
    say(c, f"✅ All {len(md_files)} markdown files have been checked")


@task
def doctest(c: Context) -> None:
    r"""Run doctests on both source code and markdown files."""
    doctest_src(c)
    doctest_markdown(c)


def _run_pytest(
    c: Context,
    path: str,
    *,
    label: str,
    timeout: int,
    cov: bool = False,
    append: bool = False,
    skip_missing: bool = False,
    args: str | None = None,
    paths: str | None = None,
) -> None:
    r"""Run pytest on a directory of tests.

    The command is ``python -m pytest [--xdoctest] --timeout <timeout>``
    followed by the coverage options and the path. ``--xdoctest`` is used
    unless ``tasklib.test.xdoctest`` is false, and
    ``--cov-fail-under`` is used with ``cov`` if
    ``tasklib.test.cov_fail_under`` is set.

    Args:
        c: The invoke context.
        path: The directory (or file) of tests.
        label: The name of the scope, used in the messages, e.g.
            ``"unit tests"``.
        timeout: The timeout in seconds of each test.
        cov: If True, generate coverage reports in HTML, XML and terminal
            formats.
        append: If True and ``cov`` is True, append to the coverage data
            of the previous runs instead of replacing it.
        skip_missing: If True, a message is written and nothing is run
            when ``path`` is not an existing directory. It is ignored
            when ``paths`` is set.
        args: Extra arguments passed to pytest, placed before the paths.
        paths: Paths of the user that replace ``path``.

    Raises:
        UnexpectedExit: If pytest fails.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import MockContext
    >>> from invoke_tasklib.testing import _run_pytest
    >>> cfg = {"tasklib": {"package": {"name": "mypkg"}}}
    >>> c = MockContext(config=Config(overrides=cfg), run=True)
    >>> _run_pytest(c, "tests/unit", label="unit tests", timeout=10)  # doctest: +ELLIPSIS
    🧪 Running unit tests...
    ...
    ✅ Unit tests complete

    ```
    """
    cfg = load_config(c)
    if skip_missing and not paths and not _directory_exists(c, path, label):
        return
    options = cfg.test
    say(c, f"🧪 Running {label}...")
    cmd = [f"{python_executable()} -m pytest"]
    if options.xdoctest:
        cmd.append("--xdoctest")
    cmd.append(f"--timeout {timeout}")
    if cov:
        cmd.extend(f"--cov-report {report}" for report in options.cov_reports)
        if append:
            cmd.append("--cov-append")
        cmd.append(f"--cov={cfg.package.import_name}")
        if options.cov_fail_under is not None:
            cmd.append(f"--cov-fail-under={options.cov_fail_under}")
        say(c, "📊 Coverage reports will be generated" + (" (appending)" if append else ""))
    run(c, build_command(" ".join(cmd), args=args, paths=paths, default_paths=[path]))
    say(c, f"✅ {label.capitalize()} complete")


@task(name="all", help=PYTEST_HELP)
def all_(c: Context, cov: bool = False, args: str | None = None, paths: str | None = None) -> None:
    r"""Run all tests (unit, integration, and functional).

    The whole tests directory is run in one pytest call, so the timeout
    of each test is the largest of the three scopes
    (``tasklib.test.unit_timeout``, ``integration_timeout`` and
    ``functional_timeout``).

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports in HTML, XML, and terminal
            formats. Default is False.
        args: Extra arguments passed to pytest, e.g. ``"-k foo -x"``.
        paths: The files or directories to run instead of the tests
            directory.
    """
    cfg = load_config(c)
    options = cfg.test
    timeout = max(options.unit_timeout, options.integration_timeout, options.functional_timeout)
    _run_pytest(
        c,
        cfg.paths.tests,
        label="all tests",
        timeout=timeout,
        cov=cov,
        args=args,
        paths=paths,
    )


@task(help=PYTEST_HELP)
def unit(c: Context, cov: bool = False, args: str | None = None, paths: str | None = None) -> None:
    r"""Run unit tests.

    The timeout of each test is ``tasklib.test.unit_timeout`` (10
    seconds by default). If the unit tests directory does not exist
    (a flat ``tests`` layout), the whole tests directory is run
    instead; if neither exists, nothing is run.

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports. Default is False.
        args: Extra arguments passed to pytest, e.g. ``"-k foo -x"``.
        paths: The files or directories to run instead of the tests of
            this scope.
    """
    cfg = load_config(c)
    path = cfg.paths.unit_tests
    if not paths and not Path(path).is_dir() and Path(cfg.paths.tests).is_dir():
        say(c, f"⏭️  No '{path}' directory: running '{cfg.paths.tests}' instead")
        path = cfg.paths.tests
    _run_pytest(
        c,
        path,
        label="unit tests",
        timeout=cfg.test.unit_timeout,
        cov=cov,
        args=args,
        paths=paths,
        skip_missing=True,
    )


@task(help=PYTEST_HELP)
def integration(
    c: Context, cov: bool = False, args: str | None = None, paths: str | None = None
) -> None:
    r"""Run integration tests.

    The timeout of each test is ``tasklib.test.integration_timeout`` (60
    seconds by default). Nothing is run if the directory does not exist.

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports, appended to the
            existing coverage data. Default is False.
        args: Extra arguments passed to pytest, e.g. ``"-k foo -x"``.
        paths: The files or directories to run instead of the tests of
            this scope.
    """
    cfg = load_config(c)
    _run_pytest(
        c,
        cfg.paths.integration_tests,
        label="integration tests",
        timeout=cfg.test.integration_timeout,
        cov=cov,
        args=args,
        paths=paths,
        append=True,
        skip_missing=True,
    )


@task(help=PYTEST_HELP)
def functional(
    c: Context, cov: bool = False, args: str | None = None, paths: str | None = None
) -> None:
    r"""Run functional tests.

    The timeout of each test is ``tasklib.test.functional_timeout`` (60
    seconds by default). Nothing is run if the directory does not exist.

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports, appended to the
            existing coverage data. Default is False.
        args: Extra arguments passed to pytest, e.g. ``"-k foo -x"``.
        paths: The files or directories to run instead of the tests of
            this scope.
    """
    cfg = load_config(c)
    _run_pytest(
        c,
        cfg.paths.functional_tests,
        label="functional tests",
        timeout=cfg.test.functional_timeout,
        cov=cov,
        args=args,
        paths=paths,
        append=True,
        skip_missing=True,
    )


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
    run(c, f"{python_executable()} -m coverage html")
    run(c, f"{python_executable()} -m coverage report")
    if open_browser:
        say(c, "🌐 Opening coverage report in the browser...")
        run(c, f"{python_executable()} -m webbrowser -t htmlcov/index.html")
    say(c, "✅ Coverage report generated in htmlcov/")


@task
def benchmark(c: Context) -> None:
    r"""Run performance benchmarks."""
    cfg = load_config(c)
    benchmarks = cfg.paths.benchmarks
    if not _directory_exists(c, benchmarks, "benchmarks"):
        return
    say(c, "⏱️  Running benchmarks...")
    run(c, f"{python_executable()} -m pytest {shlex.quote(benchmarks + '/')} --benchmark-only")
    say(c, "✅ Benchmarks complete")
