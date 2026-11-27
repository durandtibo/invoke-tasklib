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
re-exported by `config/__init__.py`; the private attributes of the Invoke config are read in
`config/_invoke.py` only) is the single source of truth for project-specific values.
It:

- Reads the `tasklib` key from the Invoke config (`c.config`), which Invoke itself populates from
  `invoke.yaml`.
- Merges it on top of the defaults declared in `SCHEMA` (`default_config()` and
  the JSON schema are loops over it; `default_config()` registers an `Unset` for every key so Invoke
  reads the environment variables as text).
- Rejects unknown keys and validates the values (`package.python_version`, `package.import_name`,
  `groups.*`, `test.*`, `check.tasks`, `fix.tasks`).
- Derives unset `paths.*` entries from `package.import_name` (for `paths.src`) or `paths.tests` (for
  the `unit_tests`/`integration_tests`/`functional_tests`/`benchmarks` entries).
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
    types: TypesConfig
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

Nine small modules support the task modules (three public ones, `runner`, `tools` and `output`,
and six private ones):

- `runner.py`: `run(c, command)` is the only way a task runs an external command. It checks that
  the program is on the `PATH` (with `tools.check_program`), echoes the command, and
  uses a pty only on a terminal. `capture(c, command)` is `run` for a command whose output the task
  reads (output hidden, command not echoed, no pty, so stderr is not merged into stdout).
  `in_ci()` and `in_github_actions()` are the only readers of `CI` and `GITHUB_ACTIONS`.
  `build_command` builds the list of the words of a command (the words, the split `--args`, the
  paths), `run` is the only place that turns the list into a shell line (`shlex.join`) and it
  rejects a string, `ARGS_HELP`/`PATHS_HELP` are the help of the `--args` and `--paths` options, and
  `TOOL_HELP` is the `help` of a task that has both.
- `tools.py`: finds the tools that the tasks run: `find_tool` looks a program up on the `PATH` or
  a module up for the running interpreter, `check_program` checks the first word of a command (and
  the module of `python -m <module>` and the plugins of the pytest options), and `hint` and
  `not_found_message` say how to install a tool. Every program and module is one `Tool` of
  `tools.TOOLS` (name, kind, dependency group or install hint, pytest options for a plugin);
  `hint(name)` is one lookup in it, `_PLUGIN_OPTIONS` (option to plugin) is derived from it, and
  `env.check-tools` loops over it.
- `output.py`: `say(c, message)` prints a progress message (it never fails on a terminal that
  cannot encode the emojis) and the `step` context manager prints the start and done messages of a
  step, or a failure message.
- `_steps.py`: the step runner shared by `check.all` and `fix.all` (`run_composite`, called by
  each of them with its own `_STEPS`, valid names and config): the selection of the steps
  (`--only`, `--skip` and the config), the look-up of the missing tools before anything runs, the
  `--keep-going` mode and the final summary of the failures.
- `_files.py`: `project_files(c, root, suffix)` finds the files with a suffix, with
  `git ls-files` in a git work tree and with `find_files`, a walk in Python (no `find` or `xargs`)
  that skips the `EXCLUDED_DIRS` of `_files.py` at any depth, otherwise. It is used by the format
  and test tasks that work on shell scripts and markdown files.
- `_pyproject.py`: `read_pyproject(path)` reads `pyproject.toml` (`{}` if the file is missing). An
  invalid file exits with `1` and a message that names the file, the line and the column of the
  error. `release` (the `[project] version`) and `_coverage` use it; `clean` ignores the error,
  because it must work on a broken project.
- `_coverage.py`: `coverage_outputs(reports, pyproject)` returns the HTML directory and the report
  files, from the `--cov-report` arguments, then `[tool.coverage.*]`, then the coverage.py defaults.
  `testing` and `clean` use it.
- `_files.py` also has `require_path(path, key)`, which exits with 2 and names the config key when a
  path that a task is about does not exist (`paths.src`, `paths.docs_config`); the module docstring
  and the user guide give the rule for the other paths.
- `_graph.py`: the static import graph of a package (built with `ast`, without importing
  anything) and its cycles. It is used by `imports.check-cycles`.
- `_discover.py`: lists the modules of a package without importing them, and imports each one in its
  own interpreter (`import_each`, called in process by `imports.check-isolated`).

`_files.EXCLUDED_DIRS` is the one list of the directories that the tasks that walk the file tree
(`clean`, `format`, `test.doctest-markdown`) never enter. It is the union of three named sets:
`CACHE_DIRS` (`.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.tox`, `.nox`, `.hypothesis`,
`.benchmarks`, `.coverage_html`), `OUTPUT_DIRS` (`build`, `dist`, `site`, `htmlcov`) and
`ENVIRONMENT_DIRS` (`.git`, `.venv`, `node_modules`). `clean._DIRS` derives from `CACHE_DIRS` and
the outputs it removes, so a cache added to the sets is cleaned and skipped by the walks. The format
and test tasks find their files with `_files.project_files`: in a git work tree they ask
`git ls-files --cached --others --exclude-standard`, so `.gitignore` is the policy and a tracked
`build/run.sh` is checked (only the caches and the environments are left out); outside a work tree
they walk the tree and skip every directory of the list. `clean` keeps its own walk, because the
`__pycache__` directories it removes are ignored by git.

### Adding a step to `check.all` or `fix.all`

A step is a `Step(task, programs, modules, default)` of `_steps.py` (the task, the programs it looks
up on the `PATH`, the Python modules it imports, and whether it runs when `check.tasks` or
`fix.tasks` is not set). `modules` is a tuple, or a function of the config that returns one, for a
step whose modules depend on an option (`check._unit_modules`). `_STEPS` is the only list of the
step names, in the order of the run; the composite checks the names of the config, `--only` and
`--skip` against it before any step runs. To add one:

1. Write the task in its module, and add `"name": Step(task, programs=..., modules=...)` to
   `check._STEPS` (or `fix._STEPS`), at the place where it must run. Pass `default=False` if it must
   not run unless the config or `--only` asks for it.
2. Add each new program or module to `TOOLS` of `tools.py` as a `Tool` with its dependency group
   (or an install hint), and the pytest options of a plugin: `env.check-tools`, the hints and the
   check of the plugins read it (a test checks that every tool of `_STEPS` is listed).
3. Update the tables of the user guide (`uguide/check.md`, `uguide/fix.md`).

### 3. The Namespace

`invoke_tasklib/__init__.py` has `make_ns(*, exclude=(), include=None)`, which builds a new
`Collection` by adding each task module (`Collection.from_module(module, name=...)`) as a
sub-collection named after the module, leaving out the tasks of `exclude` and keeping only the tasks
of `include` when it is set. The modules whose names would shadow the standard library or a builtin
(`format`, `types`, `test`) are named `formatting`, `typecheck` and `testing`; the namespace name of
each module is its `NAMESPACE` constant (`"format"` in `formatting.py`), which `_MODULES` of
`__init__.py` reads, not the module name; a project that builds its own collection passes
`name=module.NAMESPACE` to `Collection.from_module`.

This is what gives consuming projects `format.check-python`, `test.unit`, etc. via `ns = make_ns()`
in their `tasks.py`, or a trimmed copy with `make_ns(exclude=...)`. Each call returns a new
collection, so a project can add its own tasks without affecting other importers. The package has
no module-level `ns`: a collection shared by every importer would let one project's `add_task` leak
into another, so `from invoke_tasklib import ns` raises an `ImportError` and a project calls
`make_ns()` instead.

## Layers

A module imports only from its own layer or from the ones below it. The task modules (L3) do
not import each other, and neither do the composites (L4). `tests/unit/test_architecture.py`
checks the rule on the package itself.

```text
L5  __init__          make_ns: one Collection per module
L4  check  fix        composites: run _STEPS with the step runner
L3  formatting lint typecheck testing env release doc security imports clean show
L2  _steps  _files  _graph  _discover  _coverage  _pyproject   private helpers of the tasks
L1  config/  runner  tools  output     support: the documented helpers
```

No import breaks the rule; the test fails if one appears.

## Properties

These are the properties that the package guarantees to a project that uses it (`P1`-`P12`) and to
the people who change it (`M1`-`M6`). The last column says what enforces each one; a property marked
"not tested" is a rule that the code follows but no test enforces.

| #   | Property                | Statement                                                                                                                                                                                                                                                                                                                                   | Enforced by                                                                                                         |
| --- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| P1  | One entry point         | The config is read with `load_config`, a command runs through `runner.run` or `runner.capture`, a message goes through `output.say`, `step` or `report_failure`. The only environment variables read are `INVOKE_TASKLIB_<SECTION>_<KEY>`, `INVOKE_TASKLIB_ASCII`, `CI`, `GITHUB_ACTIONS`, `PATH` and the publish credentials of `release`. | `test_architecture.py` (AST scan of `src/`); not tested: the readers of `os.environ`                                |
| P2  | Read-only is read-only  | `check_<x>`, `check.all`, `test.*`, `types.*`, `imports.*`, `security.audit` and `config.show` never change a tracked file. Their only writes are caches and the coverage reports.                                                                                                                                                          | `tests/integration/test_read_only.py`                                                                               |
| P3  | Mutation is declared    | A task that changes files, the environment or a remote is named `fix_*`, or is a verb (`publish`, `build`, `install`, `clean`), and is marked in the README table.                                                                                                                                                                          | `test_init.py` (names, summaries, options); `tests/integration/test_readme.py`                                      |
| P4  | Exit codes              | `0` pass, or nothing to do (a `⏭️` line says why); `1` the checked thing failed; `2` invalid usage or config; `127` a tool or module is missing. The failure line is `❌ Failed: <what>` on stderr. With `--keep-going`, every step runs and every failure of an `Exception` is listed in the summary.                                      | `tests/integration/test_exit_codes.py`; `test__steps.py` (any `Exception`)                                          |
| P5  | Fail before acting      | An unknown key, an invalid value or a wrong working directory exits with `2` before any command runs. The message names the key.                                                                                                                                                                                                            | `config/_validate.py`, `_check_project_root`; `tests/unit/config/`                                                  |
| P6  | Missing tools           | A missing program or Python module is reported with the command that installs it. A composite task reports all the missing tools of its steps at once, and runs nothing.                                                                                                                                                                    | `tools.hint`, `_steps.preflight_message`; `tests/unit/test_check.py`                                                |
| P7  | Commands are data       | A task builds a command as a list of words; `runner.run` is the only place that turns it into a shell line (`shlex.join`) and it rejects a string. A space, `;`, `*`, `~` or `$VAR` in a user value reaches the tool unchanged.                                                                                                             | `test_architecture.py` (no `shlex.quote` or `shlex.split` outside `runner.py`); `tests/integration/test_quoting.py` |
| P8  | One source of truth     | A config key is declared once (`SCHEMA`), a tool once (`TOOLS`), a step once (`_STEPS`, with its order and whether it is a default), a directory policy once (`_files`). Defaults, the JSON schema, the hints and the docs tables derive from them.                                                                                         | tests that compare the tables; `test_clean.py` (every directory of `clean._DIRS` is in `EXCLUDED_DIRS`)             |
| P9  | Safe by default         | A destructive task stays inside the project, keeps what git tracks, and asks before an irreversible step. A credential never appears in a command line or in the output.                                                                                                                                                                    | `clean._is_inside_project`, `release._check_release_state`, `_publish_environment`; `tests/unit/test_release.py`    |
| P10 | Skips are visible       | A task that has nothing to do prints `⏭️ <reason>` and exits `0`. A task that cannot do its job (a path it needs is missing) exits non-zero and names the key.                                                                                                                                                                              | `_files.require_path`; `tests/unit/test__files.py`, `tests/integration/test_files.py`                               |
| P11 | Fix converges           | After `fix_<x>` (or `fix.all`) the matching `check_<x>` (or `check.all --only` the same steps) passes, and a second `fix_<x>` changes nothing.                                                                                                                                                                                              | `tests/integration/test_fix_converges.py`                                                                           |
| P12 | Composition is explicit | `make_ns(include=, exclude=)` selects the tasks that the command line offers. The steps of `check.all` and `fix.all` come only from `tasklib.check.tasks` and `tasklib.fix.tasks`; excluding a task from the namespace does not remove its step.                                                                                            | `test_init.py` (the selection); not tested: that an excluded task keeps its step                                    |
| M1  | Layers                  | A task module imports only the support modules, never another task module. The two composites (`check`, `fix`) import task modules and `_steps`. `config`, `tools` and `output` import nothing of the package that is above them.                                                                                                           | `test_architecture.py` (layering test)                                                                              |
| M2  | Public means documented | A name of `config`, `runner`, `tools` or `output` is public only if it is in the `__all__` of its module and in `uguide/custom_tasks.md`. Everything else starts with `_`; a task module has no public name except its tasks and `NAMESPACE`.                                                                                               | `test_architecture.py`                                                                                              |
| M3  | Every function tested   | Every function, private ones included, has a docstring, a unit test and, if the unit test patches a collaborator, an integration test. Coverage is 100% (lines and branches). A function has no parameter that every caller passes with the same value.                                                                                     | `test_docstrings.py`, `--cov-fail-under=100`; the last sentence is a review rule                                    |
| M4  | Cheap to import         | `import invoke_tasklib` stays below 100 ms; `make_ns()` does no I/O.                                                                                                                                                                                                                                                                        | `tests/benchmarks/test_init_benchmark.py`, nightly `ci-benchmark.yaml`                                              |
| M5  | Invoke internals apart  | The private attributes of `invoke.config.Config` are read in one module, `config/_invoke.py`, which warns when one is missing. No other module calls `getattr` or `hasattr` on a config for a name that starts with `_`.                                                                                                                    | `test_architecture.py` (AST scan of `src/` for `getattr`/`hasattr` of a private name)                               |
| M6  | Declared equals run     | The programs and modules that a `Step` declares are exactly those that its task runs with a check. A tool that a task runs and the step does not declare would be missing from the preflight (P6); one that is declared and not run blocks a step for nothing.                                                                              | `test_check.py` and `test_fix.py` record the commands of every step                                                 |

The tool tables are kept consistent by the same test module: every program and module named by a
step of `check._STEPS` or `fix._STEPS` is in `tools.TOOLS`, and (M6) is the one that the task of the
step runs with a check.

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
Task builds the pytest command, a list of words, with build_command
    ↓
runner.run(c, cmd) checks the program (tools.check_program), quotes the words (shlex.join),
echoes the command and executes it with c.run (pty only on a terminal)
```

## Design Choices

The design makes a few choices that shape how the package is used and extended. Each one has a
cost, and the alternative is given, so you can judge whether the current design fits your project
or what to change if it does not.

### One shared `load_config` instead of per-task config

Every task that needs a project value calls `load_config(c)`. A single resolution function keeps
the defaults and the validation of the config in one place, and every task sees the same resolved
paths (`test.unit` and `types.check` agree on `package.name`).

- **Cost**: each task resolves the config again instead of once per run. This is cheap, because
  `load_config` reads `c.config` and checks at most whether the source directory exists.
- **Alternative**: let each task read the keys it needs. The tasks would be independent, but the
  defaults and the checks would be repeated, and an invalid value would fail in some tasks and not
  in others.

### `check_<target>` and `fix_<target>` instead of a `--fix` flag

The read-only task and the task that changes files are two tasks with two names. The name tells
you what a task does before you run it, and CI can run every `check_*` task knowing that none
changes the working tree (P2, P3).

- **Cost**: more task names than a single `format` task with a `--fix` flag.
- **Alternative**: one task per tool with a flag. The list is shorter, but a task that changes
  files looks the same as one that does not, and `check.all` could not be proven read-only.

### Frozen dataclasses instead of a dict

`load_config` returns a tree of frozen dataclasses. The type checker catches a typo such as
`cfg.path.src`, attribute access reads better than nested keys, and a task cannot modify the
config that other tasks read.

- **Cost**: the dataclasses do not validate on construction. `get_config` validates the values
  when a task starts, not when the collection is loaded, because the `invoke.yaml` values are only
  known once Invoke has built the context. Each section also has a class next to its `SCHEMA`
  options, and a test keeps the two equal.
- **Alternative**: a runtime schema library (pydantic, attrs validators). It validates on
  construction, but it adds a dependency to a package that only needs `invoke`.

### One declaration per fact

A config key is declared once (`SCHEMA`), a tool once (`TOOLS`), a step once (`_STEPS`) and a
directory policy once (`_files`). The defaults, the JSON schema, the environment variable names, the
install hints and the tables of the docs are derived from them, or compared with them by a test, so
adding a key or a step is a short, local change (P8).

- **Cost**: the declarations are data structures that you read through, not plain functions, so
  they take a little longer to learn.
- **Alternative**: write each list where it is used. It is simpler to read, but the lists drift
  apart.

### Step names are checked by the composite, not by the config

The names in `tasklib.check.tasks` and `tasklib.fix.tasks` are checked by `check.all` and `fix.all`
against `_STEPS`, before any step runs. The list of names exists in one place, and adding a step is
two edits (the entry of `_STEPS` and the entry of `TOOLS`).

- **Cost**: a typo in `check.tasks` only fails when `check.all` runs, not in an unrelated task such
  as `test.unit`, and `config.show` does not flag it. The JSON schema describes the value as a
  string or a list of strings, so an editor cannot complete the step names.
- **Alternative**: keep the names in `config/_constants.py` and validate them in the config. The
  editor completes them and every task fails early, at the price of one more place to edit when you
  add a step.

### Commands are lists of words, not strings

A task builds a command with `build_command`, and `runner.run` is the only place that turns the
list into a shell line with `shlex.join`. It rejects a string. A path with a space, a glob or a
`$VAR` in a user value reaches the tool unchanged (P7), and the quoting rule is enforced by code
instead of by the discipline of each task author.

- **Cost**: a custom task cannot pass a ready-made shell string to `run`. A shell pipeline needs its
  own `c.run`, outside the helpers.
- **Alternative**: accept strings. It is more flexible, but every task must remember to quote.

### `make_ns()` builds a new collection on each call

`make_ns(include=..., exclude=...)` returns a new `Collection` each time. A project selects the
tasks it wants and adds its own without any effect on another importer (P12).

- **Cost**: the namespace is built by a call in `tasks.py`, not by an import. Excluding a task
  removes it from the command line but not from the steps of `check.all` and `fix.all`, which only
  come from the config.
- **Alternative**: a pre-built `ns`. It is one line shorter, but the instance is shared, and a
  mutation by one importer is seen by every other.

### `imports.check-isolated` runs in the same process

`imports.check-isolated` imports each module in its own fresh interpreter, so a module cannot hide
a missing import behind another one. `_discover.import_each` starts these interpreters and the task
calls it directly, with no intermediate worker process. A worker would only help if the `sys.path`
of the task differed from the one of the project, and the check of the project root makes sure it
does not.

- **Cost**: the task trusts the working directory. It exits with `2` if it is not the project root.
- **Alternative**: a worker process per task. It isolates more, and it adds a second entry point
  to maintain.

### Names are private until the user guide needs them

Only a name of `config`, `runner`, `tools` or `output` that is in `__all__` and in
`uguide/custom_tasks.md` is public (M2). The module constants, such as `clean._DIRS`, start with
an underscore.

- **Cost**: a project that wants one of these constants has to copy it, or ask for it to become
  public.
- **Alternative**: export everything. It is convenient, but every name becomes part of the API
  that you have to keep stable.

### Linux and macOS only

The tasks rely on a POSIX shell for the quoting of the commands (P7). On Windows `make_ns` emits a
`RuntimeWarning` and the platform is not supported.

- **Cost**: a Windows project cannot rely on the tasks.
- **Alternative**: abstract the shell. It is possible, but it needs a test matrix on Windows and a
  different quoting rule.

## Testing Strategy

Tests use `invoke.context.MockContext`, which records every `c.run(...)` call (made by
`runner.run`) without executing it. This lets tests assert on the exact shell command a task would
run, without depending on `ruff`, `pytest`, `uv`, etc. being installed or configured in the test
environment. The unit tests also patch `shutil.which` (an autouse fixture in
`tests/unit/conftest.py`) so that the check of the `PATH` done by
`invoke_tasklib.tools.check_program` (called by `runner.run`) passes on any machine.

## Limits and Extension Points

What the current design does not cover, and where you would change it:

1. **Task modules**: a new concern (for example changelog generation) is a new module with its own
   `NAMESPACE`, registered in `_MODULES`. See [Adding a New Task](development.md#adding-a-new-task).
2. **Validation in CI without running a task**: `config.show` validates the config, and an editor
   checks `invoke.yaml` against the published JSON schema, but no command validates the file on its
   own. A project that wants this runs `inv config.show` in CI.
3. **Step names in the schema**: the JSON schema does not list the valid step names (see
   [Design Choices](#design-choices)). The names are in `uguide/check.md` and `uguide/fix.md`.

## References

- [Invoke documentation](https://docs.pyinvoke.org/)
- [`uv` documentation](https://docs.astral.sh/uv/)
- [`mike` documentation](https://github.com/jimporter/mike)
