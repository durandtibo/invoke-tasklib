r"""Test and benchmark tasks."""

from __future__ import annotations

import os
import shlex
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.tasks import task

from invoke_tasklib.config import EXCLUDED_DIRS, load_config
from invoke_tasklib.output import say, step
from invoke_tasklib.runner import (
    ARGS_HELP,
    PATHS_HELP,
    _split,
    build_command,
    python_executable,
    run,
)

if TYPE_CHECKING:
    from invoke.context import Context

    from invoke_tasklib.config import TasklibConfig

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
    >>> c = Context(config=Config())
    >>> _ = _directory_exists(c, "no/such/dir", "benchmarks")
    ⏭️  No 'no/such/dir' directory: skipping benchmarks

    ```
    """
    if Path(path).is_dir():
        return True
    say(c, f"⏭️  No '{path}' directory: skipping {what}")
    return False


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def doctest_src(c: Context, args: str | None = None, paths: str | None = None) -> None:
    r"""Run doctests on source code.

    The command always has ``--xdoctest``, whatever the value of
    ``tasklib.test.xdoctest``, which only applies to the test scopes.
    If the ``xdoctest`` package is missing, the task stops with a
    message that names it.

    Args:
        c: The invoke context.
        args: Extra arguments passed to pytest.
        paths: The files or directories to run on instead of
            ``paths.src``.
    """
    cfg = load_config(c)
    src = cfg.paths.src
    with step(c, "📚 Running doctests on source code...", "✅ Doctest validation complete"):
        cmd = f"{python_executable()} -m pytest --xdoctest"
        run(c, build_command(cmd, args=args, paths=paths, default_paths=[src]))


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
    ...     found = _find_markdown_files(Path(tmp))
    ...     [p.relative_to(tmp).as_posix() for p in found]
    ...
    ['docs/a.md']

    ```
    """
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in MARKDOWN_EXCLUDED_DIRS]
        found.extend(Path(dirpath) / name for name in filenames if name.endswith(".md"))
    return sorted(found)


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def doctest_markdown(c: Context, args: str | None = None, paths: str | None = None) -> None:
    r"""Run doctests on the Python examples of the markdown files.

    Args:
        c: The invoke context.
        args: Extra arguments passed to ``python -m doctest``.
        paths: The markdown files to check instead of every markdown
            file of the project.
    """
    files = _split(paths, "--paths") or [str(f) for f in _find_markdown_files(Path())]
    say(c, f"📚 Found {len(files)} markdown files")
    if files:
        cmd = f"{python_executable()} -m doctest {_DOCTEST_OPTIONS}"
        run(c, build_command(cmd, args=args, paths=paths, default_paths=files))
    say(c, f"✅ All {len(files)} markdown files have been checked")


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
    cfg: TasklibConfig | None = None,
) -> None:
    r"""Run pytest on a directory of tests.

    The command is
    ``python -m pytest [--xdoctest] [--timeout <timeout>]`` followed by
    the coverage options and the path. ``--xdoctest`` is used unless
    ``tasklib.test.xdoctest`` is false, ``--timeout`` is used unless
    ``tasklib.test.timeout`` is false (the project does not have
    ``pytest-timeout``), and
    ``--cov-fail-under`` is used with ``cov`` if
    ``tasklib.test.cov_fail_under`` is set.

    Args:
        c: The invoke context.
        path: The directory (or file) of tests.
        label: The name of the scope, used in the messages, e.g.
            ``"unit tests"``.
        timeout: The timeout in seconds of each test. It is not used if
            ``tasklib.test.timeout`` is false.
        cov: If True, generate coverage reports in HTML, XML and
            terminal formats.
        append: If True and ``cov`` is True, append to the coverage data
            of the previous runs instead of replacing it.
        skip_missing: If True, a message is written and nothing is run
            when ``path`` is not an existing directory. It is ignored
            when ``paths`` is set.
        args: Extra arguments passed to pytest, placed before the paths.
        paths: Paths of the user that replace ``path``.
        cfg: The resolved config, if the caller already has it. If not
            set, the config is loaded.

    Raises:
        UnexpectedExit: If pytest fails.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import MockContext
    >>> from invoke_tasklib.testing import _run_pytest
    >>> cfg = {"tasklib": {"package": {"name": "mypkg"}}}
    >>> c = MockContext(config=Config(overrides=cfg), run=True)
    >>> _run_pytest(
    ...     c, "tests/unit", label="unit tests", timeout=10
    ... )  # doctest: +ELLIPSIS
    🧪 Running unit tests...
    ...
    ✅ Unit tests complete

    ```
    """
    cfg = cfg or load_config(c)
    if skip_missing and not paths and not _directory_exists(c, path, label):
        return
    options = cfg.test
    with step(c, f"🧪 Running {label}...", f"✅ {label.capitalize()} complete"):
        cmd = [f"{python_executable()} -m pytest"]
        if options.xdoctest:
            cmd.append("--xdoctest")
        if options.timeout:
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


@task(name="all", help=PYTEST_HELP)
def all_(c: Context, cov: bool = False, args: str | None = None, paths: str | None = None) -> None:
    r"""Run all tests (unit, integration, and functional).

    The whole tests directory is run in one pytest call, so the timeout
    of each test is the largest of the three scopes
    (``tasklib.test.unit_timeout``, ``integration_timeout`` and
    ``functional_timeout``). If the tests directory does not exist,
    nothing is run.

    Args:
        c: The invoke context.
        cov: If True, generate coverage reports in HTML, XML, and
            terminal formats. Default is False.
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
        cfg=cfg,
        timeout=timeout,
        cov=cov,
        args=args,
        paths=paths,
        skip_missing=True,
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
        cfg=cfg,
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
        cfg=cfg,
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
        cfg=cfg,
        timeout=cfg.test.functional_timeout,
        cov=cov,
        args=args,
        paths=paths,
        append=True,
        skip_missing=True,
    )


def _coverage_html_dir(pyproject: Path = Path("pyproject.toml")) -> str:
    r"""Return the directory of the HTML coverage report.

    Args:
        pyproject: The path of the ``pyproject.toml`` file.

    Returns:
        The ``directory`` option of ``[tool.coverage.html]``, or
        ``"htmlcov"`` (the default of coverage.py) if the file does not
        exist, cannot be parsed or does not set it.

    Example usage:

    ```pycon
    >>> from pathlib import Path
    >>> from invoke_tasklib.testing import _coverage_html_dir
    >>> _coverage_html_dir(Path("no/such/pyproject.toml"))
    'htmlcov'

    ```
    """
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return "htmlcov"
    directory = data.get("tool", {}).get("coverage", {}).get("html", {}).get("directory")
    return directory if isinstance(directory, str) and directory else "htmlcov"


@task(help={"open_browser": "Open the HTML report in the default web browser.", "args": ARGS_HELP})
def coverage_report(c: Context, open_browser: bool = False, args: str | None = None) -> None:
    r"""Generate an HTML coverage report.

    The report is built from the last recorded coverage data, and the
    terminal summary is printed. The report is written to the
    ``directory`` of ``[tool.coverage.html]`` in ``pyproject.toml``
    (``htmlcov`` by default).

    Args:
        c: The invoke context.
        open_browser: If True, open the generated HTML report in the
            default web browser. Default is False.
        args: Extra arguments passed to ``coverage report``, e.g.
            ``"--fail-under=90"``.
    """
    directory = _coverage_html_dir()
    with step(
        c, "📊 Generating coverage report...", f"✅ Coverage report generated in {directory}/"
    ):
        run(c, f"{python_executable()} -m coverage html")
        run(c, build_command(f"{python_executable()} -m coverage report", args=args))
        if open_browser:
            say(c, "🌐 Opening coverage report in the browser...")
            index = shlex.quote(f"{directory}/index.html")
            run(c, f"{python_executable()} -m webbrowser -t {index}")


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def benchmark(c: Context, args: str | None = None, paths: str | None = None) -> None:
    r"""Run performance benchmarks.

    Args:
        c: The invoke context.
        args: Extra arguments passed to pytest.
        paths: The files or directories to run on instead of
            ``paths.benchmarks``.
    """
    cfg = load_config(c)
    benchmarks = cfg.paths.benchmarks
    if not paths and not _directory_exists(c, benchmarks, "benchmarks"):
        return
    say(c, "⏱️  Running benchmarks...")
    cmd = f"{python_executable()} -m pytest --benchmark-only"
    run(c, build_command(cmd, args=args, paths=paths, default_paths=[benchmarks + "/"]))
    say(c, "✅ Benchmarks complete")
