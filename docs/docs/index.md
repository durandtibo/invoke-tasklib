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
- [Troubleshooting](troubleshooting.md)

## Why invoke-tasklib?

Most Python projects end up with a `tasks.py` that wraps the same handful of tools: `ruff`,
`pyright`, `pytest`, `docformatter`, `uv`, `mike`. Keeping those wrappers in sync across many
repositories is tedious, and small inconsistencies (a missing `--xdoctest` flag, a different
coverage flag) creep in over time.

`invoke-tasklib` centralizes these tasks in one importable package:

```python
from invoke_tasklib import ns
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

See the [user guide](uguide/config.md) for the full config schema.

## Features

`invoke-tasklib` provides a comprehensive set of tasks organized into namespaces:

### 🎨 **Format and Lint**

- `format.check-python` / `format.fix-python`: check or format code with ruff
- `format.check-docstrings` / `format.fix-docstrings`: check or format docstrings with
  docformatter
- `format.check-shell` / `format.fix-shell`: check shell scripts with shellcheck, or format them
  with shfmt
- `lint.check-lint`: check linting with ruff

[Learn more →](uguide/format.md)

### 🔬 **Type Checking**

- `types.check`: check type hints with pyright

[Learn more →](uguide/types.md)

### 🧪 **Testing**

- `test.doctest`, `test.unit`, `test.integration`, `test.functional`, `test.all`, `test.benchmark`

[Learn more →](uguide/test.md)

### 🐍 **Environment Management**

- `env.create-venv`, `env.install`, `env.update`, `env.show-installed-packages`,
  `env.show-python-config`

[Learn more →](uguide/env.md)

### 📦 **Release**

- `release.build`, `release.pypi`

[Learn more →](uguide/release.md)

### 📚 **Documentation**

- `doc.publish-dev`, `doc.publish-latest`

[Learn more →](uguide/doc.md)

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
