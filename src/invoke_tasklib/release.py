r"""Build and publish tasks (PyPI package)."""

from __future__ import annotations

import os
import shlex
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.exceptions import Exit
from invoke.tasks import task

from invoke_tasklib.config import load_config
from invoke_tasklib.output import say, step
from invoke_tasklib.runner import (
    ARGS_HELP,
    build_command,
    capture,
    in_ci,
    in_github_actions,
    run,
)
from invoke_tasklib.tools import tool_path

if TYPE_CHECKING:
    from invoke.context import Context


NAMESPACE = "release"
r"""The name of the namespace of the tasks of this module."""


def _latest_artifact(directory: Path, pattern: str) -> Path:
    r"""Return the most recently modified file matching a pattern.

    Args:
        directory: The directory to search.
        pattern: The glob pattern of the file name, e.g. ``"*.whl"``.

    Returns:
        The path of the most recently modified matching file.

    Raises:
        Exit: If no file matches the pattern.

    Example usage:

    ```pycon
    >>> import tempfile
    >>> from pathlib import Path
    >>> from invoke_tasklib.release import _latest_artifact
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     _ = (Path(tmp) / "pkg-1.0-py3-none-any.whl").write_text("")
    ...     _latest_artifact(Path(tmp), "*.whl").name
    ...
    'pkg-1.0-py3-none-any.whl'

    ```
    """
    candidates = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not candidates:
        msg = f"No file matching '{pattern}' found in '{directory}' after the build"
        raise Exit(msg, code=1)
    return candidates[-1]


def _build_targets(args: str | None) -> tuple[Path, tuple[str, ...]]:
    r"""Find what ``uv build`` produces from its arguments.

    Args:
        args: The extra arguments given to ``uv build``, as one string.

    Returns:
        A tuple ``(directory, patterns)``: the output directory
        (``--out-dir`` or ``-o``, ``dist`` by default) and the glob
        patterns of the artifacts that are built: the wheel with
        ``--wheel`` or ``-w``, the source distribution with ``--sdist``,
        both if none or both are given.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.release import _build_targets
    >>> _build_targets(None)
    (PosixPath('dist'), ('*.whl', '*.tar.gz'))
    >>> _build_targets("--wheel --out-dir out")
    (PosixPath('out'), ('*.whl',))

    ```
    """
    words = shlex.split(args or "")
    directory = Path("dist")
    for i, word in enumerate(words):
        if word in {"--out-dir", "-o"} and i + 1 < len(words):
            directory = Path(words[i + 1])
        elif word.startswith("--out-dir="):
            directory = Path(word.removeprefix("--out-dir="))
    patterns = []
    if "--wheel" in words or "-w" in words:
        patterns.append("*.whl")
    if "--sdist" in words:
        patterns.append("*.tar.gz")
    return directory, tuple(patterns or ("*.whl", "*.tar.gz"))


@task(help={"check": "Also check the package metadata with twine.", "args": ARGS_HELP})
def build(c: Context, *, check: bool = False, args: str | None = None) -> None:
    r"""Build the package and verify the built artifacts.

    The artifacts are checked to be installable. The newest wheel and
    the newest source distribution in the output directory (``dist/``,
    or ``--out-dir`` of ``--args``) are each installed in an isolated
    environment and the package is imported from it, using
    ``package.import_name``. The import runs in isolated mode
    (``python -I``), so the current directory is not on ``sys.path``:
    a package of the source tree (flat layout) cannot hide an artifact
    that does not contain it. Only the kinds that the build produces are
    verified: with ``--wheel`` or ``--sdist`` in ``--args``, the other
    kind is not.

    Args:
        c: The invoke context.
        check: If True, also check the package's PyPI metadata with
            twine. Default is False.
        args: Extra arguments passed to ``uv build``.
    """
    cfg = load_config(c)
    import_name = cfg.package.import_name
    with step(c, "📦 Building package..."):
        run(c, build_command("uv build --clear", args=args))
        directory, patterns = _build_targets(args)
        say(c, "🔍 Verifying package installation...")
        for pattern in patterns:
            artifact = _latest_artifact(directory, pattern)
            say(c, f"🔍 Verifying {artifact}...")
            run(
                c,
                f"uv run --isolated --no-project --with {shlex.quote(str(artifact))} -- "
                f"python -I -c {shlex.quote(f'import {import_name}')}",
            )
        if check:
            say(c, "🔍 Checking package metadata with twine...")
            twine = f"uvx --from {shlex.quote(TWINE_REQUIREMENT)} twine check"
            run(c, f"{twine} {shlex.quote(str(directory))}/*")


TWINE_REQUIREMENT = "twine>=6.1,<7"
r"""The version range of ``twine`` that ``release.build --check`` runs.

``uvx`` installs the latest release in this range, so a new major
version is never run without a change of this constant.
"""

TEST_PYPI_PUBLISH_URL = "https://test.pypi.org/legacy/"
r"""The upload endpoint of TestPyPI."""

TEST_PYPI_CHECK_URL = "https://test.pypi.org/simple/"
r"""The index of TestPyPI, to skip the files already uploaded."""


def _project_version(pyproject: Path) -> str | None:
    r"""Read the version of a ``pyproject.toml``.

    Args:
        pyproject: The path of the file.

    Returns:
        The ``project.version``, or ``None`` if the file does not
        exist or the version is dynamic (not written in the file).

    Raises:
        Exit: If the file cannot be parsed as TOML (code 1). The
            message names the file.

    Example usage:

    ```pycon
    >>> from pathlib import Path
    >>> from invoke_tasklib.release import _project_version
    >>> _project_version(Path("no/such/pyproject.toml")) is None
    True

    ```
    """
    if not pyproject.is_file():
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        msg = f"Cannot read the version: {pyproject} is not valid TOML ({exc})"
        raise Exit(msg, code=1) from exc
    version = data.get("project", {}).get("version")
    return version if isinstance(version, str) else None


def _head_tag(c: Context) -> str | None:
    r"""Return the tag that points at ``HEAD``.

    Args:
        c: The invoke context.

    Returns:
        The name of the tag, or ``None`` if ``HEAD`` is not tagged.

    Example usage:

    ```pycon
    >>> from invoke.context import MockContext
    >>> from invoke.runners import Result
    >>> from invoke_tasklib.release import _head_tag
    >>> cmd = "git describe --exact-match --tags HEAD"
    >>> _head_tag(MockContext(run={cmd: Result(stdout="v1.2.0\n")}))
    'v1.2.0'

    ```
    """
    result = capture(c, "git describe --exact-match --tags HEAD", warn=True)
    return result.stdout.strip() if result.ok and result.stdout.strip() else None


def _check_release_state(c: Context) -> None:
    r"""Check that the repository is in a state that can be released.

    The working tree must be clean, ``HEAD`` must be tagged and, if the
    ``pyproject.toml`` has a static version, the tag (without a leading
    ``v``) must be equal to it.

    Args:
        c: The invoke context.

    Raises:
        Exit: If one of the conditions is not met, or if the
            ``pyproject.toml`` is not valid TOML.

    Example usage:

    ```pycon
    >>> from invoke.context import MockContext
    >>> from invoke.runners import Result
    >>> from invoke_tasklib.release import _check_release_state
    >>> dirty = Result(stdout=" M a.py\n")
    >>> c = MockContext(run={"git status --porcelain": dirty})
    >>> _check_release_state(c)
    Traceback (most recent call last):
        ...
    invoke.exceptions.Exit: The working tree is not clean: ...

    ```
    """
    status = capture(c, "git status --porcelain")
    if status.stdout.strip():
        msg = "The working tree is not clean: commit or stash the changes before publishing"
        raise Exit(msg, code=1)
    tag = _head_tag(c)
    if tag is None:
        msg = "HEAD is not tagged: check out the release tag before publishing"
        raise Exit(msg, code=1)
    version = _project_version(Path("pyproject.toml"))
    if version is not None and tag.removeprefix("v") != version:
        msg = f"The tag {tag} does not match the version {version} of pyproject.toml"
        raise Exit(msg, code=1)


def _confirm(target: str) -> None:
    r"""Ask the user to confirm a publication.

    Args:
        target: What is published to, e.g. ``"PyPI"``.

    Raises:
        Exit: If the answer is not ``y`` or ``yes``, if there is no
            terminal to read the answer from (end of input), or if the
            user interrupts the question.
    """
    try:
        answer = input(f"Publish the package to {target}? This cannot be undone. [y/N] ")
    except (EOFError, KeyboardInterrupt):
        msg = "Publication not confirmed: pass --yes to publish without a terminal"
        raise Exit(msg, code=1) from None
    if answer.strip().lower() not in {"y", "yes"}:
        msg = "Publication cancelled"
        raise Exit(msg, code=1)


PUBLISH_CREDENTIAL_VARIABLES: tuple[str, ...] = (
    "UV_PUBLISH_TOKEN",
    "UV_PUBLISH_USERNAME",
    "UV_PUBLISH_PASSWORD",
)
r"""The variables from which ``uv publish`` reads its credentials."""


def _publish_environment(token: str | None) -> dict[str, str]:
    r"""Build the complete environment of ``uv publish``.

    The process environment is copied without the variables of
    ``PUBLISH_CREDENTIAL_VARIABLES``, so a credential that the job
    defines for another target is never read by ``uv publish`` (for
    example a ``UV_PUBLISH_TOKEN`` for PyPI when the task publishes to
    TestPyPI). The chosen token is then added. The command must be run
    with ``replace_env=True``, otherwise Invoke merges the environment
    into the inherited one.

    Args:
        token: The token chosen for the target, or ``None`` if there is
            none (Trusted Publishing, or a dry run).

    Returns:
        The environment, with the ``PATH`` of ``tool_path()``.

    Example usage:

    ```pycon
    >>> from unittest.mock import patch
    >>> from invoke_tasklib.release import _publish_environment
    >>> with patch.dict("os.environ", {"UV_PUBLISH_TOKEN": "old"}):
    ...     env = _publish_environment("new")
    >>> env["UV_PUBLISH_TOKEN"]
    'new'

    ```
    """
    env = {k: v for k, v in os.environ.items() if k not in PUBLISH_CREDENTIAL_VARIABLES}
    env["PATH"] = tool_path()
    if token:
        env["UV_PUBLISH_TOKEN"] = token
    return env


@task(
    help={
        "test_pypi": "Publish to TestPyPI instead of PyPI.",
        "dry_run": "Build and check, but do not upload anything.",
        "yes": "Do not ask for a confirmation (never asked when CI is on, e.g. CI=true).",
        "skip_checks": "Do not check the git state (clean tree, tagged HEAD, matching version).",
        "args": ARGS_HELP,
    }
)
def publish(
    c: Context,
    *,
    test_pypi: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    skip_checks: bool = False,
    args: str | None = None,
) -> None:
    r"""Build and publish the package to PyPI.

    Before anything is built, the task checks that the working tree is
    clean, that ``HEAD`` is tagged and that the tag matches the
    ``pyproject.toml`` version (``--skip-checks`` turns it off). Outside
    of CI (``CI`` set to something other than ``0`` and ``false``) it
    then asks for a confirmation (``--yes`` turns it off).

    The credentials are either a token or, in GitHub Actions with the
    ``id-token: write`` permission, PyPI Trusted Publishing. The token
    is read from ``PYPI_TOKEN`` (from ``TEST_PYPI_TOKEN`` with
    ``--test-pypi``, so a PyPI token is never sent to TestPyPI) or,
    without ``--test-pypi`` only, from ``UV_PUBLISH_TOKEN``, which
    ``uv publish`` reads natively. It is passed to ``uv publish``
    through its environment, so it does not appear on the command
    line. The credential variables that ``uv publish`` reads
    (``UV_PUBLISH_TOKEN``, ``UV_PUBLISH_USERNAME`` and
    ``UV_PUBLISH_PASSWORD``) are removed from its environment, and only
    the chosen token is given, so a token meant for PyPI is never sent
    to TestPyPI. ``dist/`` is cleared by the build, so only the freshly
    built artifacts are uploaded.

    Args:
        c: The invoke context.
        test_pypi: If True, publish to TestPyPI.
        dry_run: If True, run the checks and the build, and give
            ``--dry-run`` to ``uv publish``. No credentials are needed.
        yes: If True, do not ask for a confirmation.
        skip_checks: If True, do not check the git state.
        args: Extra arguments passed to ``uv publish``.

    Raises:
        Exit: If the git state is not releasable, if there are no
            credentials, or if the confirmation is refused.
    """
    target = "TestPyPI" if test_pypi else "PyPI"
    token_name = "TEST_PYPI_TOKEN" if test_pypi else "PYPI_TOKEN"
    token = os.environ.get(token_name)
    if not test_pypi:
        token = token or os.environ.get("UV_PUBLISH_TOKEN")
    trusted = in_github_actions() and bool(os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL"))
    if not (token or trusted or dry_run):
        alternative = "" if test_pypi else " (or UV_PUBLISH_TOKEN)"
        msg = (
            f"Set the {token_name}{alternative} environment variable, or run in "
            f"GitHub Actions with the id-token permission, to publish to {target}"
        )
        raise Exit(msg, code=1)
    if not skip_checks:
        _check_release_state(c)
    if not (yes or dry_run or in_ci()):
        _confirm(target)
    build(c)
    cmd = ["uv publish"]
    if test_pypi:
        cmd.append(
            f"--publish-url {shlex.quote(TEST_PYPI_PUBLISH_URL)} "
            f"--check-url {shlex.quote(TEST_PYPI_CHECK_URL)}"
        )
    if dry_run:
        cmd.append("--dry-run")
    if not token and trusted:
        cmd.append("--trusted-publishing always")
    start = "🚀 Publishing" + (" (dry run)" if dry_run else "") + "..."
    done = "✅ Dry run complete" if dry_run else "✅ Package published successfully"
    with step(c, start, done):
        run(
            c,
            build_command(" ".join(cmd), args=args),
            env=_publish_environment(token),
            replace_env=True,
        )
