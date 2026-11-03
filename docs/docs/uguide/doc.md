# Doc

:book: This page describes the `invoke_tasklib.doc` module, which provides tasks to publish
versioned documentation with [`mike`](https://github.com/jimporter/mike), on top of
[MkDocs](https://www.mkdocs.org/).

## Overview

| Task                 | Behavior                              |
| -------------------- | ------------------------------------- |
| `doc.publish-dev`    | Publishes development (unstable) docs |
| `doc.publish-latest` | Publishes latest (stable) docs        |

Both tasks read `paths.docs_config` from the [resolved config](config.md) (default:
`docs/mkdocs.yml`) and pass it to `mike` via `--config-file`.

## Publishing Development Docs

```shell
invoke doc.publish-dev
```

Deletes any previously published `main` version (if it exists) and deploys the current docs under
the `main` version with the `dev` alias, then pushes to the configured remote (typically
`gh-pages`).

## Publishing Latest (Stable) Docs

```shell
invoke doc.publish-latest
```

Determines the version to publish from the most recent git version tag (via
[`feu.local_git.get_last_version_tag_name`](https://github.com/durandtibo/feu)), truncated to
`<major>.<minor>` (e.g. `1.2`). It then deploys the current docs under that tag with the `latest`
alias, and sets `latest` as the default version shown to visitors.

To publish a specific version without looking at the git tags, pass it explicitly (this does not
need `feu`):

```shell
invoke doc.publish-latest --version 1.2
```

The task fails if there is no version tag and no `--version`, because publishing under a made-up
version would be a setup error. Pre-release versions (`1.2.0rc1`, `1.2.0a1`, `1.2.0.dev1`, ...) are
skipped, so they never become `latest`.

!!! note
Reading the git tag requires the `feu` package. Install documentation dependencies with
`invoke env.install --groups dev,docs` before running it, or pass `--version`.

## Local Preview

These tasks are meant for CI (they `--push` to the remote). To preview docs locally, run MkDocs
directly:

```shell
mkdocs serve -f docs/mkdocs.yml
```

## See Also

- [Config](config.md): where `paths.docs_config` comes from.
- [`invoke_tasklib.doc` reference](../refs/doc.md)
- [Troubleshooting](../troubleshooting.md): fixes for missing `feu` errors.
