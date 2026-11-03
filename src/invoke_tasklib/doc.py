r"""Documentation build and publishing tasks (mkdocs and mike)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from invoke.exceptions import Exit
from invoke.tasks import task

from invoke_tasklib.config import load_config
from invoke_tasklib.output import say
from invoke_tasklib.runner import run

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
    r"""Return the path of the mkdocs config file, checking that it exists.

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
    >>> cfg = {"tasklib": {"package": {"name": "mypkg"}, "paths": {"docs_config": "no/such.yml"}}}
    >>> _docs_config(Context(config=Config(overrides=cfg)))
    Traceback (most recent call last):
        ...
    invoke.exceptions.Exit: 'no/such.yml' (tasklib.paths.docs_config) does not exist: ...

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


@task
def build(c: Context) -> None:
    r"""Build the documentation and fail on any warning.

    The documentation is built with ``mkdocs build --strict`` from
    ``paths.docs_config``, so a broken link or a missing reference fails
    the task. It does not publish anything.

    Raises:
        UnexpectedExit: If mkdocs reports a warning or an error.
    """
    docs_config = _docs_config(c)
    say(c, "📚 Building the documentation...")
    run(c, f"mkdocs build --strict --config-file {docs_config}")
    say(c, "✅ Documentation built")


@task
def serve(c: Context) -> None:
    r"""Serve the documentation locally with live reload.

    The server runs until it is interrupted (``Ctrl+C``).
    """
    docs_config = _docs_config(c)
    say(c, "📚 Serving the documentation...")
    run(c, f"mkdocs serve --config-file {docs_config}")


@task
def publish_dev(c: Context) -> None:
    r"""Publish development (e.g. unstable) docs."""
    docs_config = _docs_config(c)
    say(c, "📚 Publishing development documentation...")
    say(c, "🗑️  Deleting previous 'main' version if it exists...")
    run(c, f"mike delete --config-file {docs_config} main", warn=True)
    say(c, "🚀 Deploying 'main' and 'dev' aliases...")
    run(c, f"mike deploy --config-file {docs_config} --push --update-aliases main dev")
    say(c, "✅ Development documentation published")


@task(
    help={
        "version": (
            "Version to publish, e.g. 1.2 or 1.2.3. Defaults to the last git version tag "
            "(requires feu)."
        )
    }
)
def publish_latest(c: Context, version: str | None = None) -> None:
    r"""Publish latest (e.g. stable) docs.

    The docs are published as ``<major>.<minor>`` of the version with the
    ``latest`` alias, and ``latest`` is set as the default version.
    Pre-release versions (``1.2.0rc1``) are skipped.

    Args:
        c: The invoke context.
        version: The version to publish, e.g. ``"1.2"`` or ``"1.2.3"``.
            Defaults to the last git version tag, which requires the
            ``feu`` package.

    Raises:
        Exit: If no version is given and no version tag exists, or if the
            version cannot be parsed.
    """
    docs_config = _docs_config(c)
    if version is None:
        from feu.local_git import get_last_version_tag_name  # noqa: PLC0415 (optional dependency)

        try:
            last_tag = get_last_version_tag_name()
        except RuntimeError:
            last_tag = None
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
    say(c, "📚 Publishing latest documentation...")
    say(c, f"📌 Using version tag: {tag}")
    say(c, f"🚀 Deploying '{tag}' and 'latest' aliases...")
    run(c, f"mike deploy --config-file {docs_config} --push --update-aliases {tag} latest")
    say(c, "🎯 Setting 'latest' as default...")
    run(c, f"mike set-default --config-file {docs_config} --push --allow-empty latest")
    say(c, "✅ Latest documentation published")
