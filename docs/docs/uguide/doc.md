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

Determines the latest released version from the most recent git version tag (via
[`feu.local_git.get_last_version_tag_name`](https://github.com/durandtibo/feu)), truncated to
`<major>.<minor>` (e.g. `1.2`). If no tag is found, it falls back to `0.0`.

It then deletes any previously published version with that tag, deploys the current docs under
that tag with the `latest` alias, and sets `latest` as the default version shown to visitors.

!!! note
`doc.publish-latest` requires the `feu` and `packaging` packages. Install documentation
dependencies with `invoke env.install --docs-deps` before running it.

## Local Preview

These tasks are meant for CI (they `--push` to the remote). To preview docs locally, run MkDocs
directly:

```shell
mkdocs serve -f docs/mkdocs.yml
```

## See Also

- [Config](config.md): where `paths.docs_config` comes from.
- [`invoke_tasklib.doc` reference](../refs/doc.md)
- [Troubleshooting](../troubleshooting.md): fixes for missing `feu`/`packaging` errors.
