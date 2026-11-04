# Doc

:book: This page describes the `invoke_tasklib.doc` module, which provides tasks to publish
versioned documentation with [`mike`](https://github.com/jimporter/mike), on top of
[MkDocs](https://www.mkdocs.org/).

## Overview

| Task                 | Behavior                              |
| -------------------- | ------------------------------------- |
| `doc.build`          | Builds the docs, failing on warnings  |
| `doc.serve`          | Serves the docs locally               |
| `doc.publish-dev`    | Publishes development (unstable) docs |
| `doc.publish-latest` | Publishes latest (stable) docs        |

All four tasks read `paths.docs_config` from the [resolved config](config.md) (default:
`docs/mkdocs.yml`). The two publish tasks pass it to `mike` via `--config-file`, and `doc.build` and
`doc.serve` pass it to `mkdocs`.

## Publishing Development Docs

```shell
invoke doc.publish-dev
```

Deploys the current docs under the `main` version with the `dev` alias (`mike deploy` replaces an
existing `main` version, so it is not deleted first), then pushes to the configured remote
(typically `gh-pages`). Pass `--no-push` to only commit the docs branch locally.

## Publishing Latest (Stable) Docs

```shell
invoke doc.publish-latest
```

Determines the version to publish from the highest git release tag (a tag like `v1.2.3`, read
with `git tag --list 'v[0-9]*'`; pre-release tags such as `v1.2.0rc1` are ignored), truncated to
`<major>.<minor>` (e.g. `1.2`). It then deploys the current docs under that tag with the `latest` alias, and sets `latest` as the
default version shown to visitors. Pass `--no-push` to only commit the docs branch locally.

To publish a specific version without looking at the git tags, pass it explicitly:

```shell
invoke doc.publish-latest --version 1.2
```

The task fails if there is no version tag and no `--version`, because publishing under a made-up
version would be a setup error. Pre-release versions (`1.2.0rc1`, `1.2.0a1`, `1.2.0.dev1`, ...) are
skipped, so they never become `latest`.

The task also refuses to move `latest` backwards: if a newer `<major>.<minor>` is already published
(`mike list --json`), for example when releasing a `1.1.5` backport after `1.2.0`, it fails with
`Refusing to publish 1.1 as latest`. Pass `--force` to publish the older version anyway.

## Local Preview

The publishing tasks are meant for CI (they `--push` to the remote). To check and preview docs
locally:

```shell
invoke doc.build
invoke doc.serve
```

`doc.build` runs `mkdocs build --strict`, so a broken link or a missing reference fails the task
(unlike a `mike deploy` into a throw-away branch, which does not). `doc.serve` runs `mkdocs serve`
with live reload. Both use `paths.docs_config` and need the `docs` dependency group.

`doc.build` and `doc.serve` take `--args` for `mkdocs`, for example
`invoke doc.serve --args "--dev-addr 127.0.0.1:8001"`.

## See Also

- [Config](config.md): where `paths.docs_config` comes from.
- [`invoke_tasklib.doc` reference](../refs/doc.md)
- [Troubleshooting](../troubleshooting.md): fixes for missing tools.
