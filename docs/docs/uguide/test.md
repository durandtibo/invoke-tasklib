# Test

:book: This page describes the `invoke_tasklib.testing` module, which provides tasks to run
doctests, unit/integration/functional tests, and benchmarks with `pytest`.

## Overview

| Task                    | Behavior                                                      |
| ----------------------- | ------------------------------------------------------------- |
| `test.doctest`          | Runs doctests on source code and markdown files               |
| `test.doctest-src`      | Runs doctests on source code                                  |
| `test.doctest-markdown` | Runs doctests on Python examples in markdown files            |
| `test.unit`             | Runs unit tests                                               |
| `test.integration`      | Runs integration tests                                        |
| `test.functional`       | Runs functional tests                                         |
| `test.all`              | Runs all tests (unit, integration, and functional)            |
| `test.coverage-report`  | Generates an HTML/terminal report from existing coverage data |
| `test.benchmark`        | Runs performance benchmarks                                   |

All test tasks (except `test.benchmark`, `test.doctest`, and `test.doctest-markdown`) run `pytest`
with `--xdoctest` enabled, so doctests embedded in the code under test are also collected. Set
`tasklib.test.xdoctest: false` if the project does not have the `xdoctest` package.

## Running Doctests

```shell
invoke test.doctest
```

Runs both `test.doctest-src` and `test.doctest-markdown`.

```shell
invoke test.doctest-src
```

Runs doctests against `paths.src` from the [resolved config](config.md). It always runs
`pytest --xdoctest`: `tasklib.test.xdoctest` only applies to the test scopes, since the task has no
purpose without the plugin. If the `xdoctest` package is missing, the task stops with a message that
names it; use `test.doctest-markdown` alone in a project that does not have the package.

```shell
invoke test.doctest-markdown
```

Recursively finds every `*.md` file in the project (skipping `.venv`, `.pytest_cache`, `.git`,
and `node_modules`) and runs, for each one:

```shell
python -m doctest -o NORMALIZE_WHITESPACE -o ELLIPSIS -o REPORT_NDIFF <file>.md
```

so Python code examples embedded in markdown files (README, docs, ...) stay correct and up to
date. `NORMALIZE_WHITESPACE` and `ELLIPSIS` make output comparisons more forgiving (whitespace
differences are ignored, and `...` in expected output matches any text), and `REPORT_NDIFF` gives
a readable diff when an example's output doesn't match. A markdown file with no `>>>` doctest
blocks is still visited but simply reports zero tests, so it always "passes".
The task reports the number of files it checks: the files of `--paths` when it is set, otherwise
every markdown file of the project.

## Running Tests by Scope

```shell
invoke test.unit
invoke test.integration
invoke test.functional
```

Each targets its own path (`paths.unit_tests`, `paths.integration_tests`,
`paths.functional_tests`), with a longer default timeout (60s vs 10s) for integration and
functional tests, since they typically exercise more of the system. The timeouts are the
`test.unit_timeout`, `test.integration_timeout` and `test.functional_timeout` values of the
[config](config.md). If the directory of `test.integration` or
`test.functional` does not exist, the task prints a message and skips it instead of failing with a
pytest error. `test.unit` does the same, except that when `paths.unit_tests` does not exist but
`paths.tests` does (a flat `tests/` layout), it runs the whole `paths.tests` directory.

```shell
invoke test.all
```

Runs everything in `paths.tests` in a single `pytest` invocation, with the largest of the three timeouts
(60s by default, since the integration and functional tests are part of that directory). If
`paths.tests` does not exist, the task prints a message and skips, like the other scopes.

## Coverage

Pass `--cov` to `test.unit`, `test.integration`, `test.functional`, or `test.all` to generate
coverage reports. The formats are the `test.cov_reports` value of the [config](config.md)
(`html,xml,term` by default, each one is a `--cov-report` of pytest-cov; an empty value leaves the
choice to pytest-cov):

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

If `tasklib.test.cov_fail_under` is set, it is passed as `--cov-fail-under` and the task fails when
the coverage is lower. Since the integration and functional tasks append to the existing data, run
`test.unit --cov` first (it replaces the data) or `coverage erase`, otherwise the result depends on
what was run before.

```shell
invoke test.coverage-report
```

Runs `python -m coverage` (the interpreter of the tests) to regenerate the HTML report and prints the terminal summary from whatever coverage data (`.coverage`)
is currently on disk — the data produced by an earlier `--cov` run — without re-running the tests.
Pass `--open-browser` to also open `htmlcov/index.html` in your default browser:

```shell
invoke test.coverage-report --open-browser
```

## Benchmarks

```shell
invoke test.benchmark
```

Runs `pytest --benchmark-only` against `paths.benchmarks`. This requires
[`pytest-benchmark`](https://pytest-benchmark.readthedocs.io/) to be installed. The task is skipped
with a message if `paths.benchmarks` does not exist.

`test.benchmark`, `test.doctest-src` and `test.doctest-markdown` take `--args` and `--paths`, and
`test.coverage-report` takes `--args` (for example `--fail-under=90`).

## See Also

- [Config](config.md): the `paths.*_tests` and `paths.benchmarks` config used by these tasks.
- [`invoke_tasklib.testing` reference](../refs/test.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
