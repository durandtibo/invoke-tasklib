# Test

:book: This page describes the `invoke_tasklib.test` module, which provides tasks to run
doctests, unit/integration/functional tests, and benchmarks with `pytest`.

## Overview

| Task                    | Behavior                                           |
| ----------------------- | -------------------------------------------------- |
| `test.doctest`          | Runs doctests on source code and markdown files    |
| `test.doctest-src`      | Runs doctests on source code                       |
| `test.doctest-markdown` | Runs doctests on Python examples in markdown files |
| `test.unit`             | Runs unit tests                                    |
| `test.integration`      | Runs integration tests                             |
| `test.functional`       | Runs functional tests                              |
| `test.all`              | Runs all tests (unit, integration, and functional) |
| `test.benchmark`        | Runs performance benchmarks                        |

All test tasks (except `test.benchmark`, `test.doctest`, and `test.doctest-markdown`) run `pytest`
with `--xdoctest` enabled, so doctests embedded in the code under test are also collected.

## Running Doctests

```shell
invoke test.doctest
```

Runs both `test.doctest-src` and `test.doctest-markdown`.

```shell
invoke test.doctest-src
```

Runs doctests against `paths.src` from the [resolved config](config.md).

```shell
invoke test.doctest-markdown
```

Recursively finds every `*.md` file in the project (skipping `.venv`, `.pytest_cache`, `.git`,
and `node_modules`) and runs `python -m doctest` against each one, so Python code examples
embedded in markdown files (README, docs, ...) stay correct and up to date.

## Running Tests by Scope

```shell
invoke test.unit
invoke test.integration
invoke test.functional
```

Each targets its own path (`paths.unit_tests`, `paths.integration_tests`,
`paths.functional_tests`), with a longer timeout (60s vs 10s) for integration and functional
tests, since they typically exercise more of the system.

```shell
invoke test.all
```

Runs everything in `paths.tests` in a single `pytest` invocation, with a 10s timeout.

## Coverage

Pass `--cov` to `test.unit`, `test.integration`, `test.functional`, or `test.all` to generate
coverage reports in HTML, XML, and terminal formats:

```shell
invoke test.unit --cov
```

`test.integration --cov` and `test.functional --cov` **append** to any existing coverage data
(`--cov-append`), so they compose with a prior `test.unit --cov` run to build up combined coverage
across scopes:

```shell
invoke test.unit --cov
invoke test.integration --cov
invoke test.functional --cov
```

## Benchmarks

```shell
invoke test.benchmark
```

Runs `pytest --benchmark-only` against `paths.benchmarks`. This requires
[`pytest-benchmark`](https://pytest-benchmark.readthedocs.io/) to be installed.

## See Also

- [Config](config.md): the `paths.*_tests` and `paths.benchmarks` config used by these tasks.
- [`invoke_tasklib.test` reference](../refs/test.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
