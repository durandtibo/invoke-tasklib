r"""Find where the coverage reports are written."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


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


def _coverage_option(section: str, key: str, pyproject: Mapping[str, Any]) -> str | None:
    r"""Read a string option of ``[tool.coverage.<section>]``.

    Args:
        section: The coverage.py section, e.g. ``"html"``.
        key: The option, e.g. ``"directory"``.
        pyproject: The content of the ``pyproject.toml`` file.

    Returns:
        The option, or ``None`` if the file does not set it, or sets it
        to something that is not a non-empty string.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._coverage import _coverage_option
    >>> _coverage_option("html", "directory", {})
    >>> pyproject = {"tool": {"coverage": {"html": {"directory": "h"}}}}
    >>> _coverage_option("html", "directory", pyproject)
    'h'

    ```
    """
    value = pyproject.get("tool", {}).get("coverage", {}).get(section, {}).get(key)
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
    >>> from invoke_tasklib._coverage import _report_argument
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


def _coverage_html_dir(pyproject: Mapping[str, Any]) -> str:
    r"""Return the directory of the HTML coverage report.

    Args:
        pyproject: The content of the ``pyproject.toml`` file.

    Returns:
        The ``directory`` option of ``[tool.coverage.html]``, or
        ``"htmlcov"`` (the default of coverage.py) if it is not set.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._coverage import _coverage_html_dir
    >>> _coverage_html_dir({})
    'htmlcov'

    ```
    """
    return _coverage_option("html", "directory", pyproject) or "htmlcov"


def coverage_outputs(reports: Sequence[str], pyproject: Mapping[str, Any]) -> CoverageOutputs:
    r"""Return where the coverage reports are written.

    The place of a report comes from, in this order, the argument of
    its ``--cov-report`` value (``html:cov_html``, ``xml:cov.xml``),
    the option of ``pyproject.toml`` (``directory`` of
    ``[tool.coverage.html]``, ``output`` of ``[tool.coverage.xml]``,
    ``json`` or ``lcov``), then the default of coverage.py.

    Args:
        reports: The values of ``test.cov_reports``.
        pyproject: The content of the ``pyproject.toml`` file (see
            ``read_pyproject``).

    Returns:
        The directory of the HTML report (always set, even if ``html``
        is not in ``reports``, because ``coverage-report`` writes it)
        and the files of the XML, JSON and LCOV reports that are in
        ``reports``, in the order of ``reports``, without duplicates.

    Example usage:

    ```pycon
    >>> from invoke_tasklib._coverage import coverage_outputs
    >>> coverage_outputs(["html:cov_html", "xml", "term"], {})
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
