r"""Test and benchmark tasks."""

from __future__ import annotations

import shlex
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from invoke.exceptions import Exit
from invoke.tasks import task

from invoke_tasklib._files import project_files
from invoke_tasklib.config import EXCLUDED_DIRS, load_config
from invoke_tasklib.output import report_failure, say, step
from invoke_tasklib.runner import (
    ARGS_HELP,
    PATHS_HELP,
    build_command,
    python_executable,
    run,
    split_args,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from invoke.context import Context

    from invoke_tasklib.config import TasklibConfig

NAMESPACE = "test"
r"""The name of the namespace of the tasks of this module."""


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
r"""Directories that the walk skips when looking for markdown files
outside a git work tree.

In a git work tree git decides which files are checked (a tracked
``site/index.md`` is checked), see ``project_files``.
"""

APPEND_HELP = (
    "With --cov, add to the existing coverage data (--cov-append) instead of replacing it."
)
PYTEST_HELP = {"cov": COV_HELP, "args": ARGS_HELP, "paths": PATHS_HELP}
APPEND_PYTEST_HELP = {**PYTEST_HELP, "append": APPEND_HELP}


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
def doctest_src(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
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


def _find_markdown_files(c: Context, root: Path) -> list[Path]:
    r"""Find the markdown files under a root directory.

    In a git work tree the files are the ones that git lists (the
    rules of ``.gitignore`` are followed), see ``project_files``.
    Otherwise the directories in ``MARKDOWN_EXCLUDED_DIRS`` (``.venv``,
    ``.git``, ``site``, ...) are not walked into, so a virtual
    environment or a build directory is never traversed.

    Args:
        c: The invoke context.
        root: The directory to search.

    Returns:
        The sorted paths of the ``.md`` files found.

    Example usage:

    ```pycon
    >>> import tempfile
    >>> from pathlib import Path
    >>> from invoke.config import Config
    >>> from invoke.context import MockContext
    >>> from invoke_tasklib.testing import _find_markdown_files
    >>> c = MockContext(config=Config(), run=True)
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     (Path(tmp) / "docs").mkdir()
    ...     (Path(tmp) / ".venv").mkdir()
    ...     _ = (Path(tmp) / "docs" / "a.md").write_text("")
    ...     _ = (Path(tmp) / ".venv" / "b.md").write_text("")
    ...     found = _find_markdown_files(c, Path(tmp))
    ...     [p.relative_to(tmp).as_posix() for p in found]
    ...
    ['docs/a.md']

    ```
    """
    return project_files(c, root, ".md", MARKDOWN_EXCLUDED_DIRS)


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def doctest_markdown(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Run doctests on the Python examples of the markdown files.

    Args:
        c: The invoke context.
        args: Extra arguments passed to ``python -m doctest``.
        paths: The markdown files to check instead of every markdown
            file of the project.
    """
    with report_failure(c, "📚 Running doctests on markdown files..."):
        files = split_args(paths, "--paths") or [str(f) for f in _find_markdown_files(c, Path())]
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
    ``pytest-timeout``), and ``--cov-fail-under`` is used with ``cov``
    if ``tasklib.test.cov_fail_under`` is set.

    Args:
        c: The invoke context.
        path: The directory (or file) of tests.
        label: The name of the scope, used in the messages, e.g.
            ``"unit tests"``.
        timeout: The timeout in seconds of each test. It is not used if
            ``tasklib.test.timeout`` is false.
        cov: If True, generate the coverage reports of
            ``tasklib.test.cov_reports`` (``html,xml,term`` by
            default).
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
            cmd.extend(f"--cov-report {shlex.quote(report)}" for report in options.cov_reports)
            if append:
                cmd.append("--cov-append")
            cmd.append(f"--cov={cfg.package.import_name}")
            if options.cov_fail_under is not None:
                cmd.append(f"--cov-fail-under={options.cov_fail_under}")
            say(c, "📊 Coverage reports will be generated" + (" (appending)" if append else ""))
        run(c, build_command(" ".join(cmd), args=args, paths=paths, default_paths=[path]))


@task(name="all", help=PYTEST_HELP)
def all_(
    c: Context, *, cov: bool = False, args: str | None = None, paths: str | None = None
) -> None:
    r"""Run all tests (unit, integration, and functional).

    The whole tests directory is run in one pytest call, so the timeout
    of each test is the largest of the three scopes
    (``tasklib.test.unit_timeout``, ``integration_timeout`` and
    ``functional_timeout``). If the tests directory does not exist,
    nothing is run.

    Args:
        c: The invoke context.
        cov: If True, generate the coverage reports of
            ``tasklib.test.cov_reports`` (``html,xml,term`` by
            default). Default is False.
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
def unit(
    c: Context, *, cov: bool = False, args: str | None = None, paths: str | None = None
) -> None:
    r"""Run unit tests.

    The timeout of each test is ``tasklib.test.unit_timeout`` (10
    seconds by default). If the unit tests directory does not exist
    (a flat ``tests`` layout), the whole tests directory is run
    instead; if neither exists, nothing is run.

    Args:
        c: The invoke context.
        cov: If True, generate the coverage reports of
            ``tasklib.test.cov_reports``. Default is False.
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


@task(help=APPEND_PYTEST_HELP)
def integration(
    c: Context,
    *,
    cov: bool = False,
    append: bool = False,
    args: str | None = None,
    paths: str | None = None,
) -> None:
    r"""Run integration tests.

    The timeout of each test is ``tasklib.test.integration_timeout`` (60
    seconds by default). Nothing is run if the directory does not exist.

    Args:
        c: The invoke context.
        cov: If True, generate the coverage reports of
            ``tasklib.test.cov_reports``. Default is False.
        append: If True and ``cov`` is True, add to the coverage data
            of the previous runs (``--cov-append``) instead of
            replacing it, e.g. after ``test.unit --cov``. Default is
            False.
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
        append=append,
        skip_missing=True,
    )


@task(help=APPEND_PYTEST_HELP)
def functional(
    c: Context,
    *,
    cov: bool = False,
    append: bool = False,
    args: str | None = None,
    paths: str | None = None,
) -> None:
    r"""Run functional tests.

    The timeout of each test is ``tasklib.test.functional_timeout`` (60
    seconds by default). Nothing is run if the directory does not exist.

    Args:
        c: The invoke context.
        cov: If True, generate the coverage reports of
            ``tasklib.test.cov_reports``. Default is False.
        append: If True and ``cov`` is True, add to the coverage data
            of the previous runs (``--cov-append``) instead of
            replacing it, e.g. after ``test.unit --cov``. Default is
            False.
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
        append=append,
        skip_missing=True,
    )


class CoverageOutputs(NamedTuple):
    r"""Where the coverage reports are written."""

    html_dir: str
    r"""The directory of the HTML report."""

    files: tuple[str, ...]
    r"""The files of the XML, JSON and LCOV reports requested."""


COVERAGE_FILE_REPORTS: dict[str, str] = {
    "xml": "coverage.xml",
    "json": "coverage.json",
    "lcov": "coverage.lcov",
}
r"""The default file of the reports that write a file, by format."""


def _coverage_option(section: str, key: str, pyproject: Path) -> str | None:
    r"""Read a string option of ``[tool.coverage.<section>]``.

    Args:
        section: The coverage.py section, e.g. ``"html"``.
        key: The option, e.g. ``"directory"``.
        pyproject: The path of the ``pyproject.toml`` file.

    Returns:
        The option, or ``None`` if the file does not exist, cannot be
        parsed, does not set the option, or sets it to something that
        is not a non-empty string.

    Example usage:

    ```pycon
    >>> from pathlib import Path
    >>> from invoke_tasklib.testing import _coverage_option
    >>> _coverage_option("html", "directory", Path("no/such.toml"))

    ```
    """
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    value = data.get("tool", {}).get("coverage", {}).get(section, {}).get(key)
    return value if isinstance(value, str) and value else None


def _report_argument(reports: Sequence[str], name: str) -> str | None:
    r"""Return the argument of a ``--cov-report`` value.

    Args:
        reports: The values of ``test.cov_reports``, e.g.
            ``("html:cov_html", "term")``.
        name: The format, e.g. ``"html"``.

    Returns:
        The argument after the colon of the first value of that
        format, or ``None`` if there is no such value or it has no
        argument.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.testing import _report_argument
    >>> _report_argument(["html:cov_html", "term"], "html")
    'cov_html'
    >>> _report_argument(["html", "term"], "html")

    ```
    """
    for report in reports:
        report_name, _, argument = report.partition(":")
        if report_name == name and argument:
            return argument
    return None


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
    return _coverage_option("html", "directory", pyproject) or "htmlcov"


def coverage_outputs(
    reports: Sequence[str], pyproject: Path = Path("pyproject.toml")
) -> CoverageOutputs:
    r"""Return where the coverage reports are written.

    The place of a report comes from, in this order, the argument of
    its ``--cov-report`` value (``html:cov_html``, ``xml:cov.xml``),
    the option of ``pyproject.toml`` (``directory`` of
    ``[tool.coverage.html]``, ``output`` of ``[tool.coverage.xml]``,
    ``json`` or ``lcov``), then the default of coverage.py.

    Args:
        reports: The values of ``test.cov_reports``.
        pyproject: The path of the ``pyproject.toml`` file.

    Returns:
        The directory of the HTML report (always set, even if ``html``
        is not in ``reports``, because ``coverage-report`` writes it)
        and the files of the XML, JSON and LCOV reports that are in
        ``reports``, in the order of ``reports``, without duplicates.

    Example usage:

    ```pycon
    >>> from pathlib import Path
    >>> from invoke_tasklib.testing import coverage_outputs
    >>> reports = ["html:cov_html", "xml", "term"]
    >>> coverage_outputs(reports, Path("no/such.toml"))
    CoverageOutputs(html_dir='cov_html', files=('coverage.xml',))

    ```
    """
    html_dir = _report_argument(reports, "html") or _coverage_html_dir(pyproject)
    files: dict[str, None] = {}
    for report in reports:
        name = report.partition(":")[0]
        if name in COVERAGE_FILE_REPORTS:
            files[
                _report_argument([report], name)
                or _coverage_option(name, "output", pyproject)
                or COVERAGE_FILE_REPORTS[name]
            ] = None
    return CoverageOutputs(html_dir, tuple(files))


@task(help={"open_browser": "Open the HTML report in the default web browser.", "args": ARGS_HELP})
def coverage_report(c: Context, *, open_browser: bool = False, args: str | None = None) -> None:
    r"""Generate an HTML coverage report.

    The report is built from the last recorded coverage data, and the
    terminal summary is printed. The report is written to the
    directory of the ``html:<dir>`` value of
    ``tasklib.test.cov_reports`` if there is one, else to the
    ``directory`` of ``[tool.coverage.html]`` in ``pyproject.toml``
    (``htmlcov`` by default).

    Args:
        c: The invoke context.
        open_browser: If True, open the generated HTML report in the
            default web browser. Default is False.
        args: Extra arguments passed to ``coverage report``, e.g.
            ``"--fail-under=90"``.
    """
    directory = coverage_outputs(load_config(c).test.cov_reports).html_dir
    with step(
        c, "📊 Generating coverage report...", f"✅ Coverage report generated in {directory}/"
    ):
        run(c, f"{python_executable()} -m coverage html -d {shlex.quote(directory)}")
        run(c, build_command(f"{python_executable()} -m coverage report", args=args))
        if open_browser:
            say(c, "🌐 Opening coverage report in the browser...")
            index = shlex.quote(f"{directory}/index.html")
            run(c, f"{python_executable()} -m webbrowser -t {index}")


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def benchmark(c: Context, *, args: str | None = None, paths: str | None = None) -> None:
    r"""Run performance benchmarks.

    The command is ``pytest --benchmark-only --benchmark-enable``:
    ``--benchmark-enable`` turns the benchmarks on even if the pytest
    config disables them (``--benchmark-disable`` in ``addopts``, to
    run each benchmark once in the normal test runs).

    Args:
        c: The invoke context.
        args: Extra arguments passed to pytest.
        paths: The files or directories to run on instead of
            ``paths.benchmarks``.

    Raises:
        Exit: With the code 1 if ``paths.benchmarks`` does not exist
            and ``paths`` is not given. The task is run on purpose, so
            a nightly job does not pass without measuring anything.
    """
    cfg = load_config(c)
    benchmarks = cfg.paths.benchmarks
    if not paths and not Path(benchmarks).is_dir():
        msg = f"No '{benchmarks}' directory: there is no benchmark to run"
        raise Exit(msg, code=1)
    with step(c, "⏱️  Running benchmarks...", "✅ Benchmarks complete"):
        cmd = f"{python_executable()} -m pytest --benchmark-only --benchmark-enable"
        run(c, build_command(cmd, args=args, paths=paths, default_paths=[benchmarks + "/"]))
