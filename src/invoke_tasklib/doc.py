r"""Documentation build and publishing tasks (mkdocs and mike)."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.exceptions import Exit
from invoke.tasks import task

from invoke_tasklib.config import load_config
from invoke_tasklib.output import report_failure, say, step
from invoke_tasklib.runner import ARGS_HELP, build_command, run

if TYPE_CHECKING:
    from invoke.context import Context

_VERSION_PATTERN = re.compile(r"v?(?P<major>\d+)\.(?P<minor>\d+)(?:\.\d+)*(?P<rest>.*)")
_PRERELEASE_PATTERN = re.compile(r"[-._]?(a|b|c|rc|alpha|beta|pre|preview|dev)\d*", re.IGNORECASE)


def _parse_release(version: str) -> tuple[str, bool]:
    r"""Parse a release version into its docs tag and pre-release flag.

    Args:
        version: A version such as ``"1.2.3"``, ``"v1.2"`` or
            ``"1.2.0rc1"``.

    Returns:
        A tuple ``(tag, is_prerelease)`` where ``tag`` is
        ``<major>.<minor>`` and ``is_prerelease`` is ``True`` for alpha,
        beta, release candidate and development versions.

    Raises:
        ValueError: If the version does not start with
            ``<major>.<minor>``.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.doc import _parse_release
    >>> _parse_release("1.2.3")
    ('1.2', False)
    >>> _parse_release("1.2.0rc1")
    ('1.2', True)

    ```
    """
    match = _VERSION_PATTERN.fullmatch(version.strip())
    if match is None:
        msg = f"Cannot parse the version '{version}': expected <major>.<minor>[.<patch>]"
        raise ValueError(msg)
    is_prerelease = _PRERELEASE_PATTERN.match(match.group("rest")) is not None
    return f"{match.group('major')}.{match.group('minor')}", is_prerelease


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
    if not Path(docs_config).is_file():
        msg = (
            f"'{docs_config}' (tasklib.paths.docs_config) does not exist: "
            "set the path of the mkdocs config file in invoke.yaml"
        )
        raise Exit(msg, code=2)
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


def _release_key(tag: str) -> tuple[int, int] | None:
    r"""Return the sort key of a docs version.

    Args:
        tag: The name of a version of the docs, e.g. ``"1.2"``, or of an
            alias-like version such as ``"main"``.

    Returns:
        ``(major, minor)``, or ``None`` if ``tag`` is not a release
        (``main``, ``dev``, ...).

    Example usage:

    ```pycon
    >>> from invoke_tasklib.doc import _release_key
    >>> _release_key("1.10")
    (1, 10)
    >>> _release_key("main") is None
    True

    ```
    """
    match = _VERSION_PATTERN.fullmatch(tag)
    if match is None:
        return None
    return int(match.group("major")), int(match.group("minor"))


def _last_version_tag(c: Context) -> str | None:
    r"""Return the most recent version tag of the git repository.

    A version tag is a tag such as ``v1.2.3``, sorted by version.

    Args:
        c: The invoke context.

    Returns:
        The name of the tag, or ``None`` if there is no version tag.

    Raises:
        UnexpectedExit: If ``git`` fails, for example outside of a git
            repository.

    Example usage:

    ```pycon
    >>> from invoke.context import MockContext
    >>> from invoke.runners import Result
    >>> from invoke_tasklib.doc import _last_version_tag
    >>> cmd = "git tag --list 'v[0-9]*' --sort=-v:refname"
    >>> c = MockContext(run={cmd: Result(stdout="v1.2.0\nv1.1.0\n")})
    >>> _last_version_tag(c)
    'v1.2.0'

    ```
    """
    result = run(c, "git tag --list 'v[0-9]*' --sort=-v:refname", hide=True, pty=False)
    return next(
        (tag for tag in result.stdout.split() if _VERSION_PATTERN.fullmatch(tag) is not None),
        None,
    )


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
    keys = (_release_key(version) for version in versions)
    return [key for key in keys if key is not None]


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
    result = run(c, command, hide=True, pty=False)
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
    with report_failure(c, "📚 Publishing development documentation..."):
        say(c, "📚 Publishing development documentation...")
        say(c, "🚀 Deploying 'main' and 'dev' aliases...")
        run(
            c,
            f"mike deploy --config-file {docs_config}{_push_option(push)} --update-aliases main dev",
        )
    say(c, "✅ Development documentation published")


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
        tag, is_prerelease = _parse_release(version)
    except ValueError as exc:
        raise Exit(str(exc), code=1) from exc
    if is_prerelease:
        say(c, f"⏭️  Skipping the pre-release version {version}: latest docs not published")
        return
    newest = max(_published_releases(c, docs_config), default=None)
    key = _release_key(tag)
    if not force and newest is not None and key is not None and key < newest:
        msg = (
            f"Refusing to publish {tag} as latest: {newest[0]}.{newest[1]} is already "
            "published. Use --force to publish it anyway."
        )
        raise Exit(msg, code=1)
    config_file = shlex.quote(docs_config)
    push_option = _push_option(push)
    with report_failure(c, "📚 Publishing latest documentation..."):
        say(c, "📚 Publishing latest documentation...")
        say(c, f"📌 Using version tag: {tag}")
        say(c, f"🚀 Deploying '{tag}' and 'latest' aliases...")
        run(
            c, f"mike deploy --config-file {config_file}{push_option} --update-aliases {tag} latest"
        )
        say(c, "🎯 Setting 'latest' as default...")
        run(c, f"mike set-default --config-file {config_file}{push_option} --allow-empty latest")
    say(c, "✅ Latest documentation published")
