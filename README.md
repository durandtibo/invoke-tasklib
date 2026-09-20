# invoke-tasklib

Reusable Invoke tasks shared across Python projects.

## Usage

Add `invoke-tasklib` as a dev dependency, then in your project's `tasks.py`:

```python
from invoke_tasklib import ns
```

and set the required config in `invoke.yaml` at the project root:

```yaml
tasklib:
  package:
    name: my_package
```

Run `invoke --list` to see the available tasks (`lint.*`, `test.*`, `env.*`,
`release.*`).

### Config

Only `tasklib.package.name` is required. Everything else has a default derived
from it. Full schema:

```yaml
tasklib:
  package:
    name: my_package        # required
    python_version: "3.12"  # used by env.create-venv
  paths:
    src: src/my_package               # default: src/<package.name>
    tests: tests
    unit_tests: tests/unit            # default: <tests>/unit
    integration_tests: tests/integration  # default: <tests>/integration
    benchmarks: tests/benchmarks      # default: <tests>/benchmarks
    docs_config: docs/mkdocs.yml
```

### Composing a custom subset of tasks

If a project needs a different set of tasks, or a one-off task alongside the
shared ones, import individual task modules instead of the pre-built `ns`:

```python
from invoke import Collection
from invoke_tasklib import lint, test

from . import my_custom_task

ns = Collection(lint, test, my_custom_task)
```

Prefer adding a config knob to a shared task over forking it; reserve custom
composition for things that are genuinely one-off to a single project.
