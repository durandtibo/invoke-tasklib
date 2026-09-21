# Architecture and Design

This document describes the internal architecture and design principles of `invoke-tasklib`.

## Overview

`invoke-tasklib` is designed around a simple idea: task modules are plain
[Invoke](https://www.pyinvoke.org/) collections that share one config-resolution function. The
core design follows these principles:

1. **One config entry point**: every task reads project-specific values through
   `invoke_tasklib.config.get_config`, never directly from `c.config`.
2. **Convention over configuration**: sensible defaults derived from `package.name` mean most
   projects only set one value (`tasklib.package.name`).
3. **Composability**: the pre-built `ns` namespace is a convenience; any subset of task modules
   can be imported and combined with project-specific tasks.
4. **No hidden state**: tasks only run external commands (`ruff`, `pytest`, `uv`, `mike`, ...);
   they don't maintain state between invocations.

## Core Components

### 1. Config Resolution

`invoke_tasklib.config.get_config(c)` is the single source of truth for project-specific values.
It:

- Reads the `tasklib` key from the Invoke config (`c.config`), which Invoke itself populates from
  `invoke.yaml`.
- Merges it on top of `DEFAULT_PACKAGE`/`DEFAULT_PATHS`.
- Derives unset `paths.*` entries from `package.name` (for `paths.src`) or `paths.tests` (for the
  `unit_tests`/`integration_tests`/`functional_tests`/`benchmarks` entries).
- Raises `ValueError` if `package.name` is missing, since nearly every task needs it.

```python
class TasklibConfig(TypedDict):
    package: PackageConfig
    paths: PathsConfig
```

Returning a `TypedDict` rather than a raw dict gives task authors static typing on
`cfg["package"]["name"]` and similar accesses.

### 2. Task Modules

Each task module (`format.py`, `lint.py`, `types.py`, `test.py`, `env.py`, `release.py`, `doc.py`)
is a flat collection of `@task`-decorated functions. A module groups tasks that operate on the
same underlying tool or concern (e.g. all of `test.py` wraps `pytest`).

Tasks that need project-specific values call `get_config(c)` at the top of the function body;
tasks that don't (e.g. `lint.check_lint`) skip it entirely.

### 3. The `ns` Namespace

`invoke_tasklib/__init__.py` builds a single `Collection` (`ns`) by adding each task module as a
sub-collection, named after the module:

```python
ns = Collection()
ns.add_collection(Collection.from_module(format), name="format")
...
```

This is what gives consuming projects `format.check-python`, `test.unit`, etc. via a single
`from invoke_tasklib import ns` in their `tasks.py`.

## Data Flow

Here's how a task invocation flows through the system:

```text
User runs `invoke test.unit --cov`
    ↓
Invoke loads invoke.yaml into c.config
    ↓
test.unit(c, cov=True) is called
    ↓
get_config(c) resolves package.name and paths.unit_tests
    ↓
Task builds the pytest command line
    ↓
c.run(cmd, pty=True) executes it as a subprocess
```

## Design Decisions

### Why a Shared `get_config` Instead of Per-Task Config?

**Rationale**: A single resolution function keeps defaults and validation in one place, and
guarantees every task sees the same resolved paths (e.g. `test.unit` and `types.check` agree on
`package.name`).

**Trade-off**: Every task pays the (cheap) cost of re-resolving config on each call, rather than
resolving it once. This is negligible since `get_config` does no I/O beyond reading `c.config`.

### Why `check_<target>`/`fix_<target>` Naming?

**Rationale**: Makes the read-only/mutating counterpart of a task discoverable by name alone, and
lets CI safely run every `check_*` task without risk of it modifying the working tree.

**Trade-off**: Slightly more verbose task names than a single `format` task with a `--fix` flag,
but the split keeps `invoke --list` self-documenting.

### Why `TypedDict` for Config?

**Rationale**: Static type checking (via pyright) catches typos like `cfg["path"]["src"]` at
development time, without requiring a runtime schema validation dependency.

**Trade-off**: `TypedDict` doesn't validate values at runtime beyond what `get_config` does
explicitly (e.g. the `package.name` check).

## Testing Strategy

Tests use `invoke.context.MockContext`, which records every `c.run(...)` call without executing
it. This lets tests assert on the exact shell command a task would run, without depending on
`ruff`, `pytest`, `uv`, etc. being installed or configured in the test environment.

## Future Directions

Potential areas for enhancement:

1. Additional task modules for other common project needs (e.g. changelog generation).
2. A `--config-schema` task to validate a project's `invoke.yaml` against the config schema
   ahead of time.

## References

- [Invoke documentation](https://docs.pyinvoke.org/)
- [`uv` documentation](https://docs.astral.sh/uv/)
- [`mike` documentation](https://github.com/jimporter/mike)
