# Check

:book: This page describes the `invoke_tasklib.check` module.

## Overview

| Task        | Behavior                                                |
| ----------- | ------------------------------------------------------- |
| `check.all` | Runs the main read-only checks of the project (default) |

`check.all` is the default task of the `check` namespace, so `invoke check` runs it.

## Usage

```shell
invoke check
```

Runs the steps of `tasklib.check.tasks`, in that order, and stops at the first failure. By default:

| Step                | Task                                   |
| ------------------- | -------------------------------------- |
| `format-python`     | [`format.check-python`](format.md)     |
| `format-docstrings` | [`format.check-docstrings`](format.md) |
| `lint`              | [`lint.check-python`](lint.md)         |
| `types`             | [`types.check`](types.md)              |
| `imports`           | [`imports.check-cycles`](imports.md)   |
| `unit`              | [`test.unit`](test.md)                 |

Other steps can be added to the config (or run with `--only`): `doctest` ([`test.doctest`](test.md)),
`shell` ([`format.check-shell`](format.md) and `format.check-shell-format`), `spelling` ([`lint.check-spelling`](lint.md)), `docs`
([`doc.build`](doc.md)) and `audit` ([`security.audit`](security.md)). They are not in the default
set because they need more tools (`shellcheck`, `shfmt`, `codespell`, `mkdocs`) or the network.

```yaml
tasklib:
  check:
    tasks: [format-python, lint, types, unit, doctest, docs]
```

None of them modifies a file. The exception is the `unit` step with `tasklib.check.cov: true`: it
runs `test.unit --cov`, which generates the coverage reports and enforces `tasklib.test.cov_fail_under`
(without it `check` never checks the threshold).

| Option         | Effect                                                                                 |
| -------------- | -------------------------------------------------------------------------------------- |
| `--keep-going` | Runs every step, prints the failed ones with the reason and exits with 1 if any failed |
| `--only`       | Comma-separated steps to run instead of `tasklib.check.tasks`                          |
| `--skip`       | Comma-separated steps to leave out                                                     |

```shell
invoke check --keep-going
invoke check --only lint,types
invoke check --skip unit
```

Before running anything, the task looks up the tools that the selected steps need and reports all the
missing ones at once (exit code 127), so a missing `ty` is not discovered after the formatting has
run. With `--keep-going`, only the steps that miss a tool are not run: they are reported as failed,
with the missing tool as the reason. Run [`env.check-tools`](env.md) to see every tool of the tasks.

By default the task stops at the first failure, as the CI jobs do; use `--keep-going` locally to
learn about all the problems in one run. A step that fails with an error of the code or of the
system (for example an `OSError`) is reported like any other failed step, with the type and the
message of the error as the reason, and the other steps still run. Use the tasks directly (with `--args` and `--paths`) to run only one
of them, or [`lint.pre-commit`](lint.md) to run the hooks of the project. To leave `check` out of a
collection, use `make_ns(exclude=["check"])`.

## See Also

- [`invoke_tasklib.check` reference](../refs/check.md)
