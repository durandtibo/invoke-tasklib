# Get Started

We highly recommend installing `invoke-tasklib` in a
[virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/)
to avoid dependency conflicts.

## Using uv (recommended)

[`uv`](https://docs.astral.sh/uv/) is a fast Python package installer and resolver:

```shell
uv add --dev invoke-tasklib
```

## Using pip

Alternatively, you can use `pip`:

```shell
pip install invoke-tasklib
```

## Setting up a project

Starting from a typical project layout:

```text
my_package/
├── src/
│   └── my_package/
│       └── __init__.py
├── tests/
│   └── unit/
├── pyproject.toml
```

### 1. Add a `tasks.py`

Add a `tasks.py` at the root of your project that imports the shared namespace:

```python
# tasks.py
from invoke_tasklib import ns
```

### 2. Add an `invoke.yaml`

Add an `invoke.yaml` at the root of your project with, at minimum, the package name:

```yaml
tasklib:
  package:
    name: my_package
```

### 3. List the available tasks

```shell
invoke --list
```

```text
Available tasks:

  doc.publish-dev              Publish development (e.g. unstable) docs.
  doc.publish-latest           Publish latest (e.g. stable) docs.
  env.create-venv              Create a virtual environment and install invoke.
  env.install                  Install project dependencies and the package in editable mode.
  env.show-installed-packages  Show the installed packages.
  env.show-python-config       Show the python configuration.
  env.update                   Update dependencies and pre-commit hooks to their latest versions.
  format.check-docstrings      Check docstring formatting with docformatter without modifying files.
  format.check-python          Check code format with ruff without modifying files.
  format.check-shell           Check shell scripts with shellcheck.
  format.fix-docstrings        Format docstrings in source code with docformatter.
  format.fix-python            Format code in place with ruff.
  format.fix-shell             Format shell scripts in place with shfmt.
  lint.check-lint              Check code linting with ruff.
  release.build                Build the package and verify it can be installed.
  release.pypi                 Build and publish the package to PyPI.
  test.all                     Run all tests (unit, integration, and functional).
  test.benchmark               Run performance benchmarks.
  test.doctest                 Run doctests on both source code and markdown files.
  test.doctest-markdown        Run doctests on Python code examples embedded in markdown files.
  test.doctest-src             Run doctests on source code.
  test.functional              Run functional tests.
  test.integration             Run integration tests.
  test.unit                    Run unit tests.
  types.check                  Check type hints with pyright.
```

### 4. Run your first tasks

```shell
invoke format.check-python lint.check-lint
invoke test.unit
```

If a task fails because a tool such as `ruff` or `pytest` isn't installed yet, run
[`env.install`](uguide/env.md) first:

```shell
invoke env.install
```

## Next Steps

- [User Guide](uguide/index.md): a full task reference organized by namespace, with an
  at-a-glance table of every task.
- [Config](uguide/config.md): the full `invoke.yaml` schema and how path defaults are derived.
- [Troubleshooting](troubleshooting.md): fixes for common setup errors (missing package name,
  missing tools, `PYPI_TOKEN`, ...).

## Installing from source

To install `invoke-tasklib` from source, you can follow the steps below.

First, clone the git repository:

```shell
git clone git@github.com:durandtibo/invoke-tasklib.git
cd invoke-tasklib
```

**Note**: `invoke-tasklib` requires Python 3.10 or higher.

It is recommended to create a virtual environment (this step is optional):

```shell
uv venv --clear
source .venv/bin/activate
```

Then, install the project in editable mode along with its development dependencies:

```shell
uv sync --group dev
```

Finally, you can test the installation by running the unit tests:

```shell
python -m pytest tests/
```
