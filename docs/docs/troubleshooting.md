# Troubleshooting & FAQ

## `ValueError: 'tasklib.package.name' must be set in invoke.yaml`

Almost every task calls [`get_config`](uguide/config.md), which requires
`tasklib.package.name`. Add an `invoke.yaml` at your project root (next to `tasks.py`) with at
least:

```yaml
tasklib:
  package:
    name: my_package
```

See [Get Started](get_started.md) and [Config](uguide/config.md) for the full schema.

## `invoke: command not found` after installing

`invoke-tasklib` depends on `invoke`, but installing a library into a virtual environment does not
always put its console scripts on `PATH` the way you expect. Make sure:

- Your virtual environment is activated (`source .venv/bin/activate`), or
- You run it via `uv run invoke ...`, or
- `invoke` itself is installed as a tool (`uv tool install invoke`, which is what
  [`env.create-venv`](uguide/env.md) does).

## `invoke --list` shows no tasks / `ns` is empty

Check that `tasks.py` actually imports and exposes `ns`:

```python
# tasks.py
from invoke_tasklib import ns
```

Invoke discovers tasks from a module-level `ns` (or `namespace`) variable in `tasks.py`; if you
renamed the import or wrapped it, Invoke won't find it.

## A task fails with "command not found" (`ruff`, `pyright`, `shellcheck`, ...)

`invoke-tasklib` tasks are wrappers around external CLI tools — it does not vendor them. Install
the missing tool, either directly or via your project's dependency groups:

```shell
invoke env.install                  # installs dev deps: ruff, pyright, pytest, ...
invoke env.install --groups dev,docs  # additionally installs mike, feu, packaging
```

`shellcheck` and `shfmt` are not Python packages; install them with your system package manager
(e.g. `brew install shellcheck shfmt` on macOS) — see the
[Format](uguide/format.md) page. The full external-tool matrix is in the
[User Guide overview](uguide/index.md#external-tools).

## `doc.publish-latest` fails with `ModuleNotFoundError: feu` / `packaging`

`doc.publish-latest` needs the `feu` and `packaging` packages to compute the version tag. Install
documentation dependencies first:

```shell
invoke env.install --groups dev,docs
```

See [Doc](uguide/doc.md).

## `release.pypi` fails to authenticate

`release.pypi` runs `uv publish --token ${PYPI_TOKEN}`. Make sure the `PYPI_TOKEN` environment
variable is set (e.g. as a CI secret) before running it:

```shell
export PYPI_TOKEN=pypi-...
invoke release.pypi
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
