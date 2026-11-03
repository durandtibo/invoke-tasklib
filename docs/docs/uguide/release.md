# Release

:book: This page describes the `invoke_tasklib.release` module, which provides tasks to build and
publish the package to PyPI using [`uv`](https://docs.astral.sh/uv/).

## Overview

| Task            | Behavior                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------- |
| `release.build` | Builds the package and verifies installation (`--check` also validates metadata with twine) |
| `release.pypi`  | Builds and publishes the package to PyPI                                                    |

## Building

```shell
invoke release.build
```

Runs `uv build`, then verifies the artifacts it produced: the newest wheel and the newest source
distribution in `dist/` are each installed in an isolated `uv run` environment
(`uv run --isolated --no-project --with dist/<file>`) and the package is imported from it.
The task fails if the build did not produce a wheel or a source distribution.

Pass `--check` to additionally validate the package's PyPI metadata with
[`twine check`](https://twine.readthedocs.io/):

```shell
invoke release.build --check
```

## Publishing to PyPI

```shell
invoke release.pypi
```

Builds the package (via `release.build`, which clears `dist/` first so stale artifacts are never
uploaded) and then runs `uv publish`. The token is read from the `PYPI_TOKEN` environment variable
(or `UV_PUBLISH_TOKEN`) and handed to `uv publish` through its environment, so it never appears on
the command line. The task fails before building if no token is set.

!!! warning
This publishes a new version to PyPI, which cannot be undone. Make sure `PYPI_TOKEN` is set
and that you are releasing the intended version before running this task.

## See Also

- [`invoke_tasklib.release` reference](../refs/release.md)
- [Troubleshooting](../troubleshooting.md): fixes for `PYPI_TOKEN` authentication errors.
