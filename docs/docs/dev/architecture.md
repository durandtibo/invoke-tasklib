# Architecture and Design

This document describes the internal architecture and design principles of `invoke-tasklib`.

## Overview

`invoke-tasklib` is designed around a simple idea: task modules are plain
[Invoke](https://www.pyinvoke.org/) collections that share one config-resolution function. The
core design follows these principles:

1. **One config entry point**: every task reads project-specific values through
   `invoke_tasklib.config.load_config` (which wraps `get_config` and exits with a message on an
   invalid config), never directly from `c.config`.
2. **Convention over configuration**: sensible defaults derived from `package.name` mean most
   projects only set one value (`tasklib.package.name`).
3. **Composability**: `make_ns()` builds the default namespace; any subset of task modules
   can be imported and combined with project-specific tasks.
4. **No hidden state**: tasks only run external commands (`ruff`, `pytest`, `uv`, `mike`, ...);
   they don't maintain state between invocations.

## Core Components

### 1. Config Resolution

`invoke_tasklib.config.get_config(c)` (implemented in `config/_resolve.py` with `load_config`, and
re-exported by `config/__init__.py`) is the single source of truth for project-specific values.
It:

- Reads the `tasklib` key from the Invoke config (`c.config`), which Invoke itself populates from
  `invoke.yaml`.
- Merges it on top of the defaults declared in `SCHEMA` (also exposed as `DEFAULT_PACKAGE`,
  `DEFAULT_PATHS`, `DEFAULT_GROUPS`, `DEFAULT_TEST`, `DEFAULT_CHECK` and `DEFAULT_FIX`).
- Rejects unknown keys and validates the values (`package.python_version`, `package.import_name`,
  `groups.*`, `test.*`, `check.tasks`, `fix.tasks`).
- Derives unset `paths.*` entries from `package.import_name` (for `paths.src`) or `paths.tests` (for the
  `unit_tests`/`integration_tests`/`functional_tests`/`benchmarks` entries).
- Raises `ValueError` if `package.name` is missing, since nearly every task needs it, or if a
  value is invalid. Tasks call `load_config`, which turns the `ValueError` into an `Exit`.

Adding a key means adding one `Option(default, validate, json_schema, doc)` to `SCHEMA` and the
field to the dataclass of its section (a test checks that they match), then one row in the
`uguide/config.md` table (a test checks that too). The known keys, the defaults, the validation, the
environment variable names and the JSON schema (`python -m invoke_tasklib.config`) follow from it.

```python
@dataclass(frozen=True)
class TasklibConfig:
    package: PackageConfig
    paths: PathsConfig
    groups: GroupsConfig
    test: TestConfig
    check: CheckConfig
    fix: FixConfig
```

Returning frozen dataclasses rather than a raw dict gives task authors static typing on
`cfg.package.name` and similar accesses, and the values cannot be modified by a task.

### 2. Task Modules

Each task module (`formatting.py`, `lint.py`, `imports.py`, `typecheck.py`, `testing.py`, `env.py`,
`release.py`, `doc.py`, `security.py`, `clean.py`, `check.py`, `fix.py`, `show.py`) is a
collection of `@task`-decorated functions. `clean.py`, `check.py` and `fix.py` also have a default
task (`clean.all`, `check.all`, `fix.all`) that is run by `invoke clean`, `invoke check` and
`invoke fix`. `check.all` and `fix.all` are the composite tasks: each runs the steps of its config
key (`tasklib.check.tasks`, `tasklib.fix.tasks`) with the step runner of `_steps.py`.
`show.py` holds `config.show`, which prints the resolved config and where each value
comes from. A module groups tasks that operate on the
same underlying tool or concern (e.g. most of `testing.py` wraps `pytest`, except
`test.doctest-markdown`, which wraps the standard library's `doctest` module directly).

Tasks that need project-specific values call `load_config(c)` at the top of the function body;
tasks that don't (e.g. `lint.check_python`) skip it entirely.

Seven small modules support the task modules:

- `runner.py`: `run(c, command)` is the only way a task runs an external command. It checks that
  the program is on the `PATH` (with `tools.check_program`), echoes the command, and
  uses a pty only on a terminal. `capture(c, command)` is `run` for a command whose output the task
  reads (output hidden, command not echoed, no pty, so stderr is not merged into stdout).
  `in_ci()` and `in_github_actions()` are the only readers of `CI` and `GITHUB_ACTIONS`.
  `build_command` builds a command line and quotes the arguments, and
  `ARGS_HELP`/`PATHS_HELP` are the help of the `--args` and `--paths` options.
- `tools.py`: finds the tools that the tasks run: `find_tool` looks a program up on the `PATH` or
  a module up for the running interpreter, `check_program` checks the first word of a command (and
  the module of `python -m <module>` and the plugins of the pytest options), and `hint` and
  `not_found_message` say how to install a tool. Every program and module is one `Tool` of
  `tools.TOOLS` (name, kind, dependency group or install hint, pytest options for a plugin);
  `PROGRAM_HINTS`, `PROGRAM_GROUPS`, `MODULE_GROUPS`, `PLUGIN_OPTIONS` and `env.TOOL_PROGRAMS` /
  `env.TOOL_MODULES` are derived from it.
- `output.py`: `say(c, message)` prints a progress message (it never fails on a terminal that
  cannot encode the emojis) and the `step` context manager prints the start and done messages of a
  step, or a failure message.
- `_steps.py`: the step runner shared by `check.all` and `fix.all`: the selection of the steps
  (`--only`, `--skip` and the config), the look-up of the missing tools before anything runs, the
  `--keep-going` mode and the final summary of the failures.
- `_files.py`: `project_files(c, root, suffix, excluded)` finds the files with a suffix, with
  `git ls-files` in a git work tree and with `find_files`, a walk in Python (no `find` or `xargs`)
  that skips the `EXCLUDED_DIRS` at any depth, otherwise. It is used by the format and test tasks
  that work on shell scripts and markdown files.
- `_graph.py`: the static import graph of a package (built with `ast`, without importing
  anything) and its cycles. It is used by `imports.check-cycles`.
- `_discover.py`: lists the modules of a package without importing them. It is run in a
  subprocess by `imports.check-isolated`.

`config.EXCLUDED_DIRS` lists the directories that the tasks that walk the file tree (`clean`,
`format`, `test.doctest-markdown`) never enter (`.venv`, `.git`, `node_modules`, ...). The format and
test tasks find their files with `_files.project_files`: in a git work tree they ask
`git ls-files --cached --others --exclude-standard`, so `.gitignore` is the policy and there is no
list of directories to maintain (the `EXCLUDED_DIRS` are still left out); outside a work tree they
walk the tree and skip the excluded directories. `clean` keeps its own walk, because the
`__pycache__` directories it removes are ignored by git.

### Adding a step to `check.all` or `fix.all`

A step is a `Step(task, programs, modules)` of `_steps.py` (the task, the programs it looks up on the
`PATH`, the Python modules it imports). `modules` is a tuple, or a function of the config that
returns one, for a step whose modules depend on an option (`check._unit_modules`). To add one:

1. Write the task in its module, and add `"name": Step(task, programs=..., modules=...)` to
   `check.STEPS` (or `fix.STEPS`).
2. Add the name to `CHECK_STEPS` (or `FIX_STEPS`) in `config/_constants.py`: the config must not
   import the task modules, and a test checks that the names agree with `STEPS`.
3. Add each new program or module to `TOOLS` of `tools.py` as a `Tool` with its dependency group
   (or an install hint), and the pytest options of a plugin: `env.check-tools`, the hints and the
   check of the plugins read it (a test checks that every tool of `STEPS` is listed).
4. To run the step by default, put it among the first steps of `CHECK_STEPS` (or `FIX_STEPS`) and
   extend `DEFAULT_CHECK_STEPS` (or `DEFAULT_FIX_STEPS`) in `config/_constants.py`, which derive the
   default of `check.tasks` (or `fix.tasks`) in `config/_schema.py`; update the tables of the user
   guide (`uguide/check.md`, `uguide/fix.md`).

### 3. The Namespace

`invoke_tasklib/__init__.py` has `make_ns(*, exclude=(), include=None)`, which builds a new
`Collection` by adding each task module (`Collection.from_module(module, name=...)`) as a
sub-collection named after the module, leaving out the tasks of `exclude` and keeping only the
tasks of `include` when it is set. The modules whose names would shadow the standard library or a
builtin (`format`, `types`, `test`) are named `formatting`, `typecheck` and `testing`; the
namespace name of each module is its `NAMESPACE` constant (`"format"` in `formatting.py`), which `_MODULES`
of `__init__.py` reads, not the module name; a project that builds its own collection passes
`name=module.NAMESPACE` to `Collection.from_module`.

This is what gives consuming projects `format.check-python`, `test.unit`, etc. via
`ns = make_ns()` in their `tasks.py`, or a trimmed copy with `make_ns(exclude=...)`. Each call returns
a new collection, so a project can add its own tasks without affecting other importers. (The
module-level `invoke_tasklib.ns`, one collection shared by every importer, was removed: use
`ns = make_ns()`.)

## Layers

A module imports only from its own layer or from the ones below it. The task modules (L3) do
not import each other, and neither do the composites (L4). `tests/unit/test_architecture.py`
checks the rule on the package itself.

```text
L5  __init__          make_ns: one Collection per module
L4  check  fix        composites: run STEPS with the step runner
L3  formatting lint typecheck testing env release doc security imports clean show
L2  _steps  _files  _graph             private helpers of the tasks
L1  config/  runner  tools  output     support: the documented helpers
L0  _discover                          worker run in a subprocess
```

One import breaks the rule today, `clean -> testing`
(`KNOWN_VIOLATIONS` in the test); the test fails if a new one appears.

## Properties

These are the properties that the package guarantees to a project that uses it. The last column
says what enforces each one.

| #   | Property               | Statement                                                                                                                  | Enforced by                                                 |
| --- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| P1  | One entry point        | The config is read with `load_config`, a command runs through `runner.run` or `capture`, a message goes through `output`.  | `test_architecture.py` (AST scan of `src/`)                 |
| P2  | Read-only is read-only | `check_<x>`, `check.all`, `test.*`, `types.check`, `imports.*`, `security.audit` and `config.show` change no tracked file. | `tests/integration/test_read_only.py`                       |
| P4  | Exit codes             | `0` pass or nothing to do, `1` the checked thing failed, `2` invalid usage or config, `127` a tool or module is missing.   | `tests/integration/test_exit_codes.py`                      |
| P5  | Fail before acting     | An unknown key, an invalid value or a wrong working directory exits with `2` before any command runs.                      | `config/_validate.py`; `tests/unit/config/`                 |
| P7  | Commands are data      | A task builds one command string from the config and the options, and every user value is quoted.                          | `runner.build_command`; `tests/integration/test_quoting.py` |
| M1  | Layers                 | See the previous section.                                                                                                  | `test_architecture.py`                                      |
| M3  | Every function tested  | Every function, private ones included, has a docstring and a unit test. Coverage is 100%.                                  | `test_docstrings.py`, `--cov-fail-under=100`                |

The tool tables are kept consistent by the same test module: every program and module named by a
step of `check.STEPS` or `fix.STEPS` is in `tools.TOOLS`.

## Data Flow

Here's how a task invocation flows through the system:

```text
User runs `invoke test.unit --cov`
    ↓
Invoke loads invoke.yaml into c.config
    ↓
test.unit(c, cov=True) is called
    ↓
load_config(c) resolves package.name and paths.unit_tests
    ↓
Task builds the pytest command line with build_command (quoted)
    ↓
runner.run(c, cmd) checks the program (tools.check_program), echoes the command and
executes it with c.run (pty only on a terminal)
```

## Design Decisions

### Why a Shared `load_config` Instead of Per-Task Config?

**Rationale**: A single resolution function keeps defaults and the validation of the config in one place, and
guarantees every task sees the same resolved paths (e.g. `test.unit` and `types.check` agree on
`package.name`).

**Trade-off**: Every task pays the (cheap) cost of re-resolving config on each call, rather than
resolving it once. This is negligible since `load_config` does no I/O beyond reading `c.config` and, for the defaults
that come from the project, whether the source directory exists.

### Why `check_<target>`/`fix_<target>` Naming?

**Rationale**: Makes the read-only/mutating counterpart of a task discoverable by name alone, and
lets CI safely run every `check_*` task without risk of it modifying the working tree.

**Trade-off**: Slightly more verbose task names than a single `format` task with a `--fix` flag,
but the split keeps `invoke --list` self-documenting.

### Why Frozen Dataclasses for Config?

**Rationale**: Static type checking (via ty) catches typos like `cfg.path.src` at development
time, and attribute access reads better than nested keys, without requiring a runtime schema
validation dependency.

**Trade-off**: The dataclasses don't validate values on construction; the validation is done by
`get_config` (e.g. the `package.name` and `package.python_version` checks). It runs when a task starts, not when the collection
is loaded, because the `invoke.yaml` values are only known once Invoke has built the context.

## Testing Strategy

Tests use `invoke.context.MockContext`, which records every `c.run(...)` call (made by
`runner.run`) without executing it. This lets tests assert on the exact shell command a task would run, without depending on
`ruff`, `pytest`, `uv`, etc. being installed or configured in the test environment. The unit
tests also patch `shutil.which` (an autouse fixture in `tests/unit/conftest.py`) so that the check
of the `PATH` done by `invoke_tasklib.tools.check_program` (called by `runner.run`) passes on any
machine.

## Future Directions

Potential areas for enhancement:

1. Additional task modules for other common project needs (e.g. changelog generation).
2. A task to validate a project's `invoke.yaml` against the config schema ahead of time (the
   errors of `get_config` are only raised when a task runs).

## References

- [Invoke documentation](https://docs.pyinvoke.org/)
- [`uv` documentation](https://docs.astral.sh/uv/)
- [`mike` documentation](https://github.com/jimporter/mike)
