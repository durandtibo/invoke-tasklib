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

Add a `tasks.py` at the root of your project:

```python
# tasks.py
from invoke_tasklib import ns
```

Add an `invoke.yaml` at the root of your project with, at minimum, the package name:

```yaml
tasklib:
  package:
    name: my_package
```

Then list the available tasks:

```shell
invoke --list
```

See the [user guide](uguide/config.md) for the full config schema, and the config's
[reference](refs/config.md) for implementation details.

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
