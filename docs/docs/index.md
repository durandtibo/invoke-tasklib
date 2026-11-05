# Home

<p align="center">
    <a href="https://github.com/durandtibo/invoke-tasklib/actions/workflows/ci.yaml">
        <img alt="CI" src="https://github.com/durandtibo/invoke-tasklib/actions/workflows/ci.yaml/badge.svg">
    </a>
    <a href="https://codecov.io/gh/durandtibo/invoke-tasklib">
        <img alt="Codecov" src="https://codecov.io/gh/durandtibo/invoke-tasklib/branch/main/graph/badge.svg">
    </a>
    <br/>
    <a href="https://durandtibo.github.io/invoke-tasklib/">
        <img alt="Documentation" src="https://github.com/durandtibo/invoke-tasklib/actions/workflows/release-docs.yaml/badge.svg">
    </a>
    <br/>
    <a href="https://github.com/astral-sh/ruff">
        <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff" style="max-width:100%;">
    </a>
    <br/>
    <a href="https://pypi.org/project/invoke-tasklib/">
        <img alt="PYPI version" src="https://img.shields.io/pypi/v/invoke-tasklib">
    </a>
    <a href="https://pypi.org/project/invoke-tasklib/">
        <img alt="Python" src="https://img.shields.io/pypi/pyversions/invoke-tasklib.svg">
    </a>
    <a href="https://opensource.org/licenses/BSD-3-Clause">
        <img alt="BSD-3-Clause" src="https://img.shields.io/pypi/l/invoke-tasklib">
    </a>
    <br/>
</p>

## Overview

`invoke-tasklib` is a reusable library of [Invoke](https://www.pyinvoke.org/) tasks shared across
Python projects. Instead of copy-pasting the same `tasks.py` boilerplate (formatting, linting,
type-checking, testing, environment setup, releasing, and documentation) into every repository, a
project imports one namespace and gets a consistent set of `invoke` commands.

**Quick Links:**

- [Get Started](get_started.md)
- [User Guide](uguide/index.md)
- [Config](uguide/config.md)
- [Writing a Custom Task](uguide/custom_tasks.md)
- [Troubleshooting](troubleshooting.md)

## Why invoke-tasklib?

Most Python projects end up with a `tasks.py` that wraps the same handful of tools: `ruff`,
`ty`, `pytest`, `docformatter`, `uv`, `mike`. Keeping those wrappers in sync across many
repositories is tedious, and small inconsistencies (a missing `--xdoctest` flag, a different
coverage flag) creep in over time.

`invoke-tasklib` centralizes these tasks in one importable package:

```python
from invoke_tasklib import make_ns

ns = make_ns()
```

```shell
invoke --list
```

A single `invoke.yaml` at the project root configures the package name and, optionally, the paths
used by the tasks:

```yaml
tasklib:
  package:
    name: my_package
```

See the [user guide](uguide/config.md) for the full config schema. Every key can also be set with
an `INVOKE_TASKLIB_<SECTION>_<KEY>` environment variable (for example `INVOKE_TASKLIB_PATHS_SRC`),
and an editor can check the file against the [JSON schema](schema.json).

A project that needs fewer tasks, or tasks of its own, builds the namespace with
`make_ns(exclude=[...])` or `make_ns(include=[...])`, see
[Writing a Custom Task](uguide/custom_tasks.md).

## Conventions of the Tasks

- **`check_<target>` never modifies a file and `fix_<target>` does.** `check.all` runs the
  read-only checks of the project and `fix.all` the fixers; the [Check](uguide/check.md) and
  [Fix](uguide/fix.md) pages list their steps.
- **Every tool is looked up before it runs.** A missing program or Python module is reported with
  the command that installs it (exit code `127`), and a composite task reports all the missing
  tools of its steps at once.
- **Exit codes:** `0` the task passed, or had nothing to do (a `⏭️` line says why); `1` the checked
  thing failed; `2` invalid usage or config (the message names the key); `127` a tool is missing.
- **Extra arguments:** the tasks that run a tool take `--args` and, for the tasks that work on
  files, `--paths`, see
  [Passing Arguments to the Tools](uguide/index.md#passing-arguments-to-the-tools).

## Features

`invoke-tasklib` provides a comprehensive set of tasks organized into namespaces:

### 🎨 **Format and Lint**

- `format.check-python` / `format.fix-python`: check or format code with ruff
- `format.check-docstrings` / `format.fix-docstrings`: check or format docstrings with
  docformatter
- `format.check-shell` / `format.check-shell-format` / `format.fix-shell`: check shell scripts with
  shellcheck, check their format with shfmt, or format them with shfmt
- `lint.check-python` / `lint.fix-python`: check or fix linting with ruff
- `lint.check-spelling`: check the spelling with codespell
- `lint.pre-commit`: run all the pre-commit hooks

[Learn more →](uguide/format.md)

### 🔁 **Cyclic Imports**

- `imports.check-cycles`: check for cyclic import dependencies (static import graph)
- `imports.check-isolated`: check that every module imports on its own

[Learn more →](uguide/imports.md)

### 🔬 **Type Checking**

- `types.check`: check type hints with ty (`--complete` also runs pyright)

[Learn more →](uguide/types.md)

### 🧪 **Testing**

- `test.doctest`, `test.doctest-src`, `test.doctest-markdown`, `test.unit`, `test.integration`,
  `test.functional`, `test.all`, `test.coverage-report`, `test.benchmark`

[Learn more →](uguide/test.md)

### 🐍 **Environment Management**

- `env.create-venv`, `env.install`, `env.update`, `env.check-tools`, `env.show-installed-packages`,
  `env.show-python-config`

[Learn more →](uguide/env.md)

### 📦 **Release**

- `release.build`, `release.publish`

[Learn more →](uguide/release.md)

### 📚 **Documentation**

- `doc.build`, `doc.serve`, `doc.publish-dev`, `doc.publish-latest`

[Learn more →](uguide/doc.md)

### 🔒 **Security**

- `security.audit`: audit the dependencies for known vulnerabilities with pip-audit

[Learn more →](uguide/security.md)

### ✅ **Check**

- `check.all` (or `check`): run the main read-only checks

[Learn more →](uguide/check.md)

### 🔧 **Fix**

- `fix.all` (or `fix`): fix the lint and format issues

[Learn more →](uguide/fix.md)

### 🧹 **Clean**

- `clean.all` (or `clean`): remove build artifacts and caches
- `clean.pycache`: remove all `__pycache__` directories

[Learn more →](uguide/clean.md)

### ⚙️ **Config**

- `config.show`: show the resolved config and where each value comes from

[Learn more →](uguide/config.md)

## Contributing

Contributions are welcome! Please open an issue first to discuss significant changes. See the
[developer guide](dev/development.md) for how to set up a development environment and the
project's conventions.

## API Stability

:warning: **Important**: As `invoke-tasklib` is under active development, its API is not yet
stable and may change between releases. We recommend pinning a specific version in your project's
dependencies to ensure consistent behavior.

## License

`invoke-tasklib` is licensed under the BSD 3-Clause "New" or "Revised" license available in
[LICENSE](https://github.com/durandtibo/invoke-tasklib/blob/main/LICENSE).
