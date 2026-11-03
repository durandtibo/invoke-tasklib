# Get Started

We highly recommend installing `invoke-tasklib` in a
[virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/)
to avoid dependency conflicts.

## Prerequisite: uv

Most tasks (`env.*`, `release.*` and `security.audit`) run
[`uv`](https://docs.astral.sh/uv/getting-started/installation/), whichever
way `invoke-tasklib` is installed. Install it first. A task that needs it
and cannot find it stops with a hint that points to the same page.

## Using uv (recommended)

[`uv`](https://docs.astral.sh/uv/) is a fast Python package installer and resolver:

```shell
uv add --dev invoke-tasklib
```

## Using pip

Alternatively, you can use `pip` (`uv` is still needed to run the tasks
listed above):

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

  check.all (check)             Run the main checks of the project.
  clean.all (clean)             Remove build artifacts and caches.
  clean.pycache                 Remove all ``__pycache__`` directories.
  doc.build                     Build the documentation and fail on any
                                warning.
  doc.publish-dev               Publish development (e.g. unstable) docs.
  doc.publish-latest            Publish latest (e.g. stable) docs.
  doc.serve                     Serve the documentation locally with live
                                reload.
  env.create-venv               Create a virtual environment and install invoke
                                in it.
  env.install                   Install the dependencies and the package
                                (editable).
  env.show-installed-packages   Show the installed packages.
  env.show-python-config        Show the python configuration.
  env.update                    Update dependencies and pre-commit hooks.
  format.check-docstrings       Check docstring format with docformatter.
  format.check-python           Check code format with ruff without modifying
                                files.
  format.check-shell            Check shell scripts with shellcheck.
  format.fix-docstrings         Format docstrings in source code with
                                docformatter.
  format.fix-python             Format code in place with ruff.
  format.fix-shell              Format shell scripts in place with shfmt.
  imports.check-cycles          Check for cyclic imports, one module at a time.
  lint.check-python             Check code linting with ruff.
  lint.check-spelling           Check the spelling with codespell.
  lint.fix-python               Fix auto-fixable linting issues in place with
                                ruff.
  lint.pre-commit               Run all the pre-commit hooks on all the files.
  release.build                 Build the package and verify the built
                                artifacts.
  release.pypi                  Build and publish the package to PyPI.
  security.audit                Audit the dependencies for known
                                vulnerabilities.
  test.all                      Run all tests (unit, integration, and
                                functional).
  test.benchmark                Run performance benchmarks.
  test.coverage-report          Generate an HTML coverage report.
  test.doctest                  Run doctests on both source code and markdown
                                files.
  test.doctest-markdown         Run doctests on the Python examples of the
                                markdown files.
  test.doctest-src              Run doctests on source code.
  test.functional               Run functional tests.
  test.integration              Run integration tests.
  test.unit                     Run unit tests.
  types.check                   Check type hints.

```

### 4. Run your first tasks

```shell
invoke format.check-python lint.check-python
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

**Note**: `invoke-tasklib` requires Python 3.11 or higher.

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
