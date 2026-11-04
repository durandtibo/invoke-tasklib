# Release

:book: This page describes the `invoke_tasklib.release` module, which provides tasks to build and
publish the package to PyPI using [`uv`](https://docs.astral.sh/uv/).

## Overview

`release.pypi` was renamed to `release.publish`; the old name is no longer available.

| Task              | Behavior                                                                                    |
| ----------------- | ------------------------------------------------------------------------------------------- |
| `release.build`   | Builds the package and verifies installation (`--check` also validates metadata with twine) |
| `release.publish` | Checks the git state, then builds and publishes the package to PyPI or TestPyPI             |

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

`twine` is run with `uvx` from the version range `twine>=6.1,<7` (`TWINE_REQUIREMENT` in
`invoke_tasklib.release`), so a new major release is never run without a release of
`invoke-tasklib`.

## Publishing to PyPI

```shell
invoke release.publish
```

Before anything is built, the task checks the git state: the working tree must be clean, `HEAD`
must be tagged and the tag (without a leading `v`) must be the static `project.version` of
`pyproject.toml` (a dynamic version is not compared). It then asks for a confirmation, unless
`--yes` is given or the `CI` environment variable is set. Finally it builds the package (via
`release.build`, which clears `dist/` first so stale artifacts are never uploaded) and runs
`uv publish`.

Credentials, in this order:

- a token in `PYPI_TOKEN` (`TEST_PYPI_TOKEN` with `--test-pypi`, because the two indexes reject
  each other's tokens and a PyPI token must not be sent to TestPyPI) or in `UV_PUBLISH_TOKEN`,
  handed to `uv publish` through its environment so it never appears on the command line;
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OpenID Connect), used
  automatically in GitHub Actions with the `id-token: write` permission (`--trusted-publishing
always`); no token is needed.

Without either, the task fails before building.

| Option          | Effect                                                                         |
| --------------- | ------------------------------------------------------------------------------ |
| `--test-pypi`   | Publishes to [TestPyPI](https://test.pypi.org/) instead of PyPI                |
| `--dry-run`     | Runs the checks and the build, and gives `--dry-run` to `uv publish`; no token |
| `--yes`         | Does not ask for a confirmation                                                |
| `--skip-checks` | Does not check the git state                                                   |
| `--args`        | Extra arguments for `uv publish`                                               |

```shell
invoke release.publish --dry-run
invoke release.publish --test-pypi --yes
```

<!-- prettier-ignore -->
!!! warning
    This publishes a new version to PyPI, which cannot be undone. Try `--dry-run` or `--test-pypi`
    first, and make sure you are releasing the intended version.

`release.build` takes `--args` for `uv build`.

## See Also

- [`invoke_tasklib.release` reference](../refs/release.md)
- [Troubleshooting](../troubleshooting.md): fixes for `PYPI_TOKEN` authentication errors.
