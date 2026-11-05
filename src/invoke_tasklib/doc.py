r"""Documentation build and publishing tasks (mkdocs and mike)."""

from __future__ import annotations

import json
import re
import shlex
from typing import TYPE_CHECKING, NamedTuple

from invoke.exceptions import Exit
from invoke.tasks import task

from invoke_tasklib._files import require_path
from invoke_tasklib.config import load_config
from invoke_tasklib.output import say, step
from invoke_tasklib.runner import ARGS_HELP, build_command, capture, run

if TYPE_CHECKING:
    from invoke.context import Context

NAMESPACE = "doc"
r"""The name of the namespace of the tasks of this module."""

_VERSION_PATTERN = re.compile(
    r"v?(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?(?:\.\d+)*(?P<rest>.*)"
)
_PRERELEASE_PATTERN = re.compile(
    r"[-._]?(?:a|b|c|rc|alpha|beta|pre|preview|dev)(?![a-z])", re.IGNORECASE
)


class _Version(NamedTuple):
    r"""A version of the project, as the docs tasks read it.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.doc import _Version
    >>> _Version(1, 2, 3, False)[:2]
    (1, 2)

    ```
    """

    major: int
    r"""The first number."""

    minor: int
    r"""The second number."""

    patch: int
    r"""The third number, 0 if there is none."""

    prerelease: bool
    r"""Whether the version is an alpha, beta, release candidate or
    development version."""


def _parse_version(text: str) -> _Version:
    r"""Parse a version, or a version tag.

    Args:
        text: A version such as ``"1.2.3"``, ``"v1.2"`` or
            ``"1.2.0rc1"``. Numbers after the third are ignored.

    Returns:
        The numbers of the version (``patch`` is 0 if missing) and
        whether it is a pre-release: alpha, beta, release candidate and
        development versions are. A suffix that only starts like a
        pre-release keyword (``-backport``, ``-cool``, ``-alpine``) is
        not a pre-release.

    Raises:
        ValueError: If the text does not start with
            ``<major>.<minor>``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.doc import _parse_version
    >>> _parse_version("v1.2.3")
    _Version(major=1, minor=2, patch=3, prerelease=False)
    >>> _parse_version("1.2.0rc1")
    _Version(major=1, minor=2, patch=0, prerelease=True)
    >>> _parse_version("1.2.0-backport").prerelease
    False

    ```
    """
    match = _VERSION_PATTERN.fullmatch(text.strip())
    if match is None:
        msg = f"Cannot parse the version '{text}': expected <major>.<minor>[.<patch>]"
        raise ValueError(msg)
    return _Version(
        int(match["major"]),
        int(match["minor"]),
        int(match["patch"] or 0),
        _PRERELEASE_PATTERN.match(match["rest"]) is not None,
    )


def _docs_config(c: Context) -> str:
    r"""Return the path of the mkdocs config file, if it exists.

    Only the tasks that use the documentation call this function, so a
    project without documentation can use all the other tasks.

    Args:
        c: The invoke context.

    Returns:
        The value of ``paths.docs_config``.

    Raises:
        Exit: If the config is invalid, or if the file does not exist.

    Example usage:

    ```pycon
    >>> from invoke.config import Config
    >>> from invoke.context import Context
    >>> from invoke_tasklib.doc import _docs_config
    >>> paths = {"docs_config": "no/such.yml"}
    >>> package = {"name": "mypkg"}
    >>> cfg = {"tasklib": {"package": package, "paths": paths}}
    >>> _docs_config(Context(config=Config(overrides=cfg)))
    Traceback (most recent call last):
        ...
    invoke.exceptions.Exit: 'no/such.yml' ......

    ```
    """
    docs_config = load_config(c).paths.docs_config
    require_path(docs_config, "tasklib.paths.docs_config", file=True)
    return docs_config


@task(help={"args": ARGS_HELP})
def build(c: Context, *, args: str | None = None) -> None:
    r"""Build the documentation and fail on any warning.

    The documentation is built with ``mkdocs build --strict`` from
    ``paths.docs_config``, so a broken link or a missing reference fails
    the task. It does not publish anything.

    Args:
        c: The invoke context.
        args: Extra arguments passed to mkdocs.

    Raises:
        UnexpectedExit: If mkdocs reports a warning or an error.
    """
    docs_config = _docs_config(c)
    with step(c, "📚 Building the documentation...", "✅ Documentation built"):
        cmd = f"mkdocs build --strict --config-file {shlex.quote(docs_config)}"
        run(c, build_command(cmd, args=args))


@task(help={"args": ARGS_HELP})
def serve(c: Context, *, args: str | None = None) -> None:
    r"""Serve the documentation locally with live reload.

    The server runs until it is interrupted (``Ctrl+C``).

    Args:
        c: The invoke context.
        args: Extra arguments passed to mkdocs, e.g.
            ``"--dev-addr 127.0.0.1:8001"``.
    """
    docs_config = _docs_config(c)
    say(c, "📚 Serving the documentation...")
    cmd = f"mkdocs serve --config-file {shlex.quote(docs_config)}"
    run(c, build_command(cmd, args=args))


def _last_version_tag(c: Context) -> str | None:
    r"""Return the highest release version tag of the git repository.

    A version tag is a tag such as ``v1.2.3``. Pre-release tags such as
    ``v1.2.0rc1`` are ignored and the tags are compared by their
    numbers, not by git's own sort, so the result does not depend on
    the ``versionsort.suffix`` setting of git.

    Args:
        c: The invoke context.

    Returns:
        The name of the tag, or ``None`` if there is no release tag.

    Raises:
        UnexpectedExit: If ``git`` fails, for example outside of a git
            repository.

    Example usage:

    ```pycon
    >>> from invoke.context import MockContext
    >>> from invoke.runners import Result
    >>> from invoke_tasklib.doc import _last_version_tag
    >>> cmd = "git tag --list 'v[0-9]*'"
    >>> out = "v1.1.0\nv1.2.0rc1\nv1.2.0\n"
    >>> c = MockContext(run={cmd: Result(stdout=out)})
    >>> _last_version_tag(c)
    'v1.2.0'

    ```
    """
    result = capture(c, "git tag --list 'v[0-9]*'")
    releases: dict[str, _Version] = {}
    for tag in result.stdout.split():
        try:
            version = _parse_version(tag)
        except ValueError:
            continue
        if not version.prerelease:
            releases[tag] = version
    newest = max(((version[:3], tag) for tag, version in releases.items()), default=None)
    return None if newest is None else newest[1]


def _parse_releases(output: str, command: str) -> list[tuple[int, int]]:
    r"""Parse the output of ``mike list --json``.

    Args:
        output: The output of the command: a JSON list of objects with a
            ``version`` key, or nothing.
        command: The command, used in the error message.

    Returns:
        The ``(major, minor)`` of the published versions. Versions that
        are not releases, such as ``main``, are left out.

    Raises:
        Exit: If the output is not the expected JSON.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.doc import _parse_releases
    >>> out = '[{"version": "1.2"}, {"version": "main"}]'
    >>> _parse_releases(out, "mike list --json")
    [(1, 2)]

    ```
    """
    try:
        versions = [entry["version"] for entry in json.loads(output or "[]")]
    except (ValueError, TypeError, KeyError) as exc:
        msg = f"Cannot read the output of '{command}': {output!r}"
        raise Exit(msg, code=1) from exc
    releases: list[tuple[int, int]] = []
    for version in versions:
        try:
            parsed = _parse_version(version)
        except ValueError:
            continue
        releases.append((parsed.major, parsed.minor))
    return releases


def _published_releases(c: Context, docs_config: str) -> list[tuple[int, int]]:
    r"""Return the releases that are already published with mike.

    Args:
        c: The invoke context.
        docs_config: The path of the mkdocs config file.

    Returns:
        The ``(major, minor)`` of the published versions, see
        ``_parse_releases``.

    Raises:
        Exit: If the output of ``mike list --json`` is not valid JSON.
        UnexpectedExit: If ``mike`` fails.
    """
    command = f"mike list --config-file {shlex.quote(docs_config)} --json"
    result = capture(c, command)
    return _parse_releases(result.stdout, command)


def _push_option(push: bool) -> str:
    r"""Return the ``--push`` option of mike, if the docs are pushed.

    Args:
        push: Whether the docs branch is pushed.

    Returns:
        ``" --push"`` (with a leading space) or an empty string.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.doc import _push_option
    >>> _push_option(True)
    ' --push'
    >>> _push_option(False)
    ''

    ```
    """
    return " --push" if push else ""


@task(help={"push": "Push the docs branch (default). Use --no-push to only commit it locally."})
def publish_dev(c: Context, *, push: bool = True) -> None:
    r"""Publish development (e.g. unstable) docs.

    The ``main`` version is deployed with the ``dev`` alias. An existing
    ``main`` version is replaced by ``mike deploy``, so it is not
    deleted first (a failed deployment would otherwise remove it).

    Args:
        c: The invoke context.
        push: If True, the docs branch is pushed. Use ``--no-push`` to
            commit it locally only.
    """
    docs_config = shlex.quote(_docs_config(c))
    with step(
        c, "📚 Publishing development documentation...", "✅ Development documentation published"
    ):
        say(c, "🚀 Deploying 'main' and 'dev' aliases...")
        run(
            c,
            f"mike deploy --config-file {docs_config}{_push_option(push)}"
            " --update-aliases main dev",
        )


@task(
    help={
        "version": (
            "Version to publish, e.g. 1.2 or 1.2.3. Defaults to the last git version tag "
            "(a tag like v1.2.3)."
        ),
        "force": "Publish even if a newer version of the docs is already published.",
        "push": "Push the docs branch (default). Use --no-push to only commit it locally.",
    }
)
def publish_latest(
    c: Context,
    *,
    version: str | None = None,
    force: bool = False,
    push: bool = True,
) -> None:
    r"""Publish latest (e.g. stable) docs.

    The docs are published as ``<major>.<minor>`` of the version with
    the ``latest`` alias, and ``latest`` is set as the default version.
    Pre-release versions (``1.2.0rc1``) are skipped. The task refuses to
    publish a version that is older than one that is already published
    (for example a ``1.1.5`` backport after ``1.2.0``), because it would
    move ``latest`` backwards, unless ``force`` is set.

    Args:
        c: The invoke context.
        version: The version to publish, e.g. ``"1.2"`` or ``"1.2.3"``.
            Defaults to the last git version tag (``v1.2.3``).
        force: If True, publish even if a newer version is published.
        push: If True, the docs branch is pushed. Use ``--no-push`` to
            commit it locally only.

    Raises:
        Exit: If no version is given and no version tag exists, or if
            the version cannot be parsed, or if a newer version is
            already published and ``force`` is False.
    """
    docs_config = _docs_config(c)
    if version is None:
        last_tag = _last_version_tag(c)
        if last_tag is None:
            msg = "No version tag found: create a release tag or pass --version"
            raise Exit(msg, code=1)
        version = last_tag
    try:
        parsed = _parse_version(version)
    except ValueError as exc:
        raise Exit(str(exc), code=1) from exc
    if parsed.prerelease:
        say(c, f"⏭️  Skipping the pre-release version {version}: latest docs not published")
        return
    tag = f"{parsed.major}.{parsed.minor}"
    newest = max(_published_releases(c, docs_config), default=None)
    if not force and newest is not None and (parsed.major, parsed.minor) < newest:
        msg = (
            f"Refusing to publish {tag} as latest: {newest[0]}.{newest[1]} is already "
            "published. Use --force to publish it anyway."
        )
        raise Exit(msg, code=1)
    config_file = shlex.quote(docs_config)
    push_option = _push_option(push)
    with step(c, "📚 Publishing latest documentation...", "✅ Latest documentation published"):
        say(c, f"📌 Using version tag: {tag}")
        say(c, f"🚀 Deploying '{tag}' and 'latest' aliases...")
        run(
            c, f"mike deploy --config-file {config_file}{push_option} --update-aliases {tag} latest"
        )
        say(c, "🎯 Setting 'latest' as default...")
        run(c, f"mike set-default --config-file {config_file}{push_option} --allow-empty latest")
