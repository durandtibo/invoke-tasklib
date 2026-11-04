# Fix

:book: This page describes the `invoke_tasklib.fix` module.

## Overview

| Task      | Behavior                                          |
| --------- | ------------------------------------------------- |
| `fix.all` | Fixes the lint and format issues (modifies files) |

`fix.all` is the default task of the `fix` namespace, so `invoke fix` runs it. It is the counterpart
of [`check.all`](check.md), which never modifies a file.

## Usage

```shell
invoke fix
```

The steps are the ones of `tasklib.fix.tasks` (see [Config](config.md)), by default:

1. `lint`: `lint.fix-python` (`ruff check --fix`);
2. `format-python`: `format.fix-python` (`ruff format`);
3. `format-docstrings`: `format.fix-docstrings` (docformatter).

The other step is `shell` (`format.fix-shell`, shfmt). The order matters: the lint fixes run before
the formatting, which has the last word on the layout, so a second run changes nothing.

| Option         | Effect                                                         |
| -------------- | -------------------------------------------------------------- |
| `--only`       | Comma-separated steps to run instead of `tasklib.fix.tasks`    |
| `--skip`       | Comma-separated steps to leave out                             |
| `--keep-going` | Runs every step and lists the failed ones, instead of stopping |

Like `check.all`, the programs of the selected steps are looked up before anything runs, and all the
missing ones are reported at once with the exit code 127. With `--keep-going`, only the steps that
miss a tool are not run; they are reported as failed.

<!-- prettier-ignore -->
!!! warning
    The steps modify files in place. Commit your work before running them.

## See Also

- [`invoke_tasklib.fix` reference](../refs/fix.md)
- [Check](check.md): the read-only counterpart.
