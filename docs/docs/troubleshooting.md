# Troubleshooting & FAQ

## `'tasklib.package.name' must be set in invoke.yaml`

Almost every task reads the [config](uguide/config.md), which requires
`tasklib.package.name`. An invalid config is reported with this one-line message and the exit
code 2. Add an `invoke.yaml` at your project root (next to `tasks.py`) with at
least:

```yaml
tasklib:
  package:
    name: my_package
```

See [Get Started](get_started.md) and [Config](uguide/config.md) for the full schema.

## `inv must run from the project root, where tasks.py is: ...`

Invoke looks for `tasks.py` in the parents of the current directory and loads the `invoke.yaml`
next to it, but it does not change directory. The tasks use paths relative to the current directory
(`tests/unit`, `pyproject.toml`, `dist`, ...), so from a subdirectory they would look in the wrong
place, and a task like `test.unit` would skip the missing `tests/unit` directory and pass. A task
that reads the config now exits with code 2 and this message instead. Run `inv` from the directory
of `tasks.py`, as in `cd <project root> && inv check.all`, or use the `make` targets.

## `'ruff' was not found on the PATH`

Before running a command, the tasks check that its program (`ruff`, `ty`, `uv`, `mike`, ...) is on
the `PATH` and exit with code 127 if it is not. Install the project tools with
`invoke env.install` (the `dev` group has the linters and test tools, the `docs` group has `mike`)
or activate the virtual environment that has them. Run `invoke env.check-tools` to list every missing
tool at once; `invoke check` does the same for the steps it is going to run.

The hint depends on the program: `uv` and `uvx` point to the installation page of `uv`
(`env.install` itself needs it), `git`, `shellcheck` and `shfmt` to the system package manager, and
`codespell` to the project dependencies. The tools of the `dev` group (`ruff`, `ty`, `pyright`,
`docformatter`, `pre-commit`, `pytest` and its plugins) and of the `docs` group (`mkdocs`, `mike`)
name their group, for example `uv sync --group docs`.

Only the first word of a command is checked, after the `NAME=value` words that set environment
variables. A program given by a path (`./run.sh`, `~/bin/tool`) and the shell builtins (`cd`,
`export`, `test`, `[`, `exec`, `source`, `.`, `:`) are not looked up. The command line is not parsed
as shell, so a pipeline (`a | b`), a list (`a && b`) or a subshell is not understood: pass
`check=False` to `run` to run it without the check.
The module of `python -m <module>` is checked too (for example `pytest`), and is reported as
`The Python module 'pytest' is not installed for ...` instead of Python's own `No module named`.

The pytest plugins of the options are checked as well: `--xdoctest` needs `xdoctest`, `--timeout`
needs `pytest-timeout`, `--cov*` (also `--no-cov`) needs `pytest-cov` and `--benchmark-*` needs `pytest-benchmark`.
A missing plugin is reported as `The option --xdoctest needs the pytest plugin 'xdoctest'` with the
command that adds it, instead of pytest's `unrecognized arguments`.

## `invoke: command not found` after installing

`invoke-tasklib` depends on `invoke`, but installing a library into a virtual environment does not
always put its console scripts on `PATH` the way you expect. Make sure:

- Your virtual environment is activated (`source .venv/bin/activate`), or
- You run it via `uv run invoke ...`, or
- `invoke` itself is installed as a tool (`uv tool install invoke`). Note that
  [`env.create-venv`](uguide/env.md) installs the project, with `invoke`, into the new `.venv`, not
  as a tool.

## `invoke --list` shows no tasks / `ns` is empty

Check that `tasks.py` actually builds and exposes `ns`:

```python
# tasks.py
from invoke_tasklib import make_ns

ns = make_ns()
```

Invoke discovers tasks from a module-level `ns` (or `namespace`) variable in `tasks.py`; if you
renamed the variable or wrapped it, Invoke won't find it. (The pre-built `invoke_tasklib.ns` was
removed: `from invoke_tasklib import ns` raises an `ImportError`, use `make_ns()`.)

## A task fails with "command not found" (`ruff`, `ty`, `shellcheck`, ...)

`invoke-tasklib` tasks are wrappers around external CLI tools — it does not vendor them. Run
`invoke env.check-tools` to see, in one list, which tools are available and which are missing. Install
the missing tool, either directly or via your project's dependency groups:

```shell
invoke env.install                  # installs dev deps: ruff, ty, pytest, ...
invoke env.install --groups dev,docs  # additionally installs mike
```

`shellcheck` and `shfmt` are not Python packages; install them with your system package manager
(e.g. `brew install shellcheck shfmt` on macOS) — see the
[Format](uguide/format.md) page. The full external-tool matrix is in the
[User Guide overview](uguide/index.md#external-tools).

## `doc.publish-latest` fails with `No version tag found`

`doc.publish-latest` reads the last git tag that looks like `v1.2.3`. Create a release tag (and
fetch the tags in CI: `git fetch --tags`), or skip the tag lookup by passing the version:

```shell
invoke doc.publish-latest --version 1.2
```

## `doc.publish-latest` fails with `Refusing to publish ... as latest`

A newer version of the docs is already published, so publishing this one would move `latest`
backwards. Pass `--force` if that is what you want.

See [Doc](uguide/doc.md).

## The output has `[ok]` and `[fail]` instead of emojis

On a terminal that cannot encode them (an ASCII locale, `PYTHONIOENCODING=ascii`), the progress
messages use the tags `[ok]`, `[fail]` and `[skip]` and leave the other emojis out. Use a UTF-8
locale (for example `LANG=C.UTF-8`) to get the emojis. Set `INVOKE_TASKLIB_ASCII=1` to get the
tags on any terminal, for example in a log that is read by a tool.

See [Custom tasks](uguide/custom_tasks.md).

## `release.publish` fails to authenticate

`release.publish` passes the `PYPI_TOKEN` (`TEST_PYPI_TOKEN` with `--test-pypi`, and
`UV_PUBLISH_TOKEN` without it) environment variable to `uv publish`. Without a token it only works in GitHub Actions with the `id-token: write`
permission (Trusted Publishing); anywhere else it stops with a clear message. Make sure the
variable is set (e.g. as a CI secret) before running it:

```shell
export PYPI_TOKEN=pypi-...
invoke release.publish

export TEST_PYPI_TOKEN=pypi-...
invoke release.publish --test-pypi
```

See [Release](uguide/release.md).

## `fix-python` / `fix-docstrings` / `fix-shell` changed files I didn't expect

`fix_*` tasks modify files in place by design (see the
[naming convention](uguide/format.md#overview)). Always run them on a clean working tree so the
diff is easy to review:

```shell
git status   # make sure everything is committed first
invoke format.fix-python
git diff     # review what changed
```

## My custom paths aren't picked up

Only `paths.*` keys you explicitly set in `invoke.yaml` are used; unset ones fall back to their
default, which is _derived from other keys_, not from a previous override. For example, setting
`paths.tests` also moves the default for `paths.unit_tests` (since it's derived from `paths.tests`),
but setting `paths.unit_tests` alone does not affect `paths.tests`. See
[Config → Overriding Paths](uguide/config.md#overriding-paths) for a worked example.

## Where do I ask for help / report a bug?

Open an issue on
[GitHub](https://github.com/durandtibo/invoke-tasklib/issues). See the
[developer guide](dev/development.md) if you'd like to contribute a fix.
