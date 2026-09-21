# Release

:book: This page describes the `invoke_tasklib.release` module, which provides tasks to build and
publish the package to PyPI using [`uv`](https://docs.astral.sh/uv/).

## Overview

| Task              | Behavior                                                                                     |
| ------------------ | ---------------------------------------------------------------------------------------------- |
| `release.build`   | Builds the package and verifies installation (`--check` also validates metadata with twine) |
| `release.pypi`    | Builds and publishes the package to PyPI                                                     |

## Building

```shell
invoke release.build
```

Runs `uv build`, then verifies the built wheel can actually be installed and imported by running
it in an isolated `uv run` environment.

Pass `--check` to additionally validate the package's PyPI metadata with
[`twine check`](https://twine.readthedocs.io/):

```shell
invoke release.build --check
```

## Publishing to PyPI

```shell
invoke release.pypi
```

Builds the package (via `release.build`) and then runs `uv publish`, using the `PYPI_TOKEN`
environment variable for authentication.

!!! warning
    This publishes a new version to PyPI, which cannot be undone. Make sure `PYPI_TOKEN` is set
    and that you are releasing the intended version before running this task.

## See Also

- [`invoke_tasklib.release` reference](../refs/release.md)
