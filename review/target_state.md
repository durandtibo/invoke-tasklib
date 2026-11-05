# `invoke_tasklib`: target state and the changes to reach it

This document proposes the target state of the `invoke_tasklib` package and the sequence of small
changes that gets there from `main` (`3bb705b`, `0.1.0a0`). It follows the principles of the
documentation (`docs/docs/dev/architecture.md`, `CLAUDE.md`, the user guide): one config entry
point, convention over configuration, composable tasks, no hidden state, a read-only `check_<x>`
for every mutating `fix_<x>`. Breaking changes are accepted (the package is an alpha), and the
future state weighs more than the past one. The previous review (`review/suggestions.md`) is
almost entirely done; this one does not repeat it. It looks at what is left: duplicated sources of
truth, a contract that is implied but not written down or tested, and a public surface that is
larger than the one the documentation promises.

The package is already close to the target. Most of the value of this document is in section 1
(writing the contract) and in deleting code and tables, not in adding features. It deliberately
adds no task, no dependency and no option.

**Evidence labels.** **[verified]** means reproduced by running code (the repository's `.venv`
tools, or a throwaway project outside the repository). **[reading]** means found by reading the
source and not run.

**What was not changed.** No source file or test was changed to write this document. The probes
ran in a project in the scratchpad, outside the repository. `release.publish`, `doc.publish-*`
and the workflows were not run, CI was not looked at, and the user guide and reference pages were
read only where they state a property.

**Baseline on `main`** [verified]: `pytest tests` 2964 passed, 13 skipped (the skipped tests are
the `mike` ones, the `docs` group is not installed in this environment); coverage 100% (lines and
branches, `TOTAL 1690 0 416 0`); `ty check` clean; `inv test.doctest` passes (46 markdown files).
**`ruff check src tests` reports 2 errors and `ruff format --check src tests` would reformat 5
files**, with `ruff 0.17.3`, the version pinned in `uv.lock` (see F11).

## Constraints

1. **Simple and easy to maintain.** The only runtime dependency stays `invoke`. A change is
   accepted when it deletes more than it adds, or when it turns an unwritten rule into a test. No
   plug-in system, no new option, no new abstraction layer.
2. **Breaking changes are allowed, in one release.** The version is `0.1.0a0`. The breaking steps
   below ship together in `0.1.0` and are listed in its notes. The task names, the `make_ns`
   signature and the keys of `invoke.yaml` do not change, so a project's `tasks.py` and
   `invoke.yaml` keep working.
3. **Start-up cost is a floor.** `import invoke_tasklib` takes about 60 ms and `inv --list` 90 ms
   in a project [verified]. Nothing in the target may import more than today; the benchmark
   `tests/benchmarks/test_init_benchmark.py` guards it.
4. **One convention per concern**, as in `CLAUDE.md`: read the config with `load_config`, run a
   command with `runner.run`, print with `output.say`. A rule that has no test is not a rule
   (section 8).
5. **Match the surrounding code**: docstrings, naming, test style and the three-line section
   headers of the tests stay as they are.

## 1. Properties of the sub-package

These are the properties that the package guarantees to a project that uses it (`P1`-`P10`), then
those it guarantees to its own maintainers (`M1`-`M4`). The last column says where each one is
enforced: an existing mechanism, or **new:** a test that this plan adds (section 8).

| #   | Property                | Statement                                                                                                                                                                                                                         | Enforced by                                                                                                              |
| --- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| P1  | One entry point         | The config is read with `load_config`; a command runs through `runner.run` or `runner.capture`; a message goes through `output.say`, `step` or `report_failure`. No task calls `c.run`, `print` or reads `c.config` directly.     | `grep` finds no violation today [verified]; **new:** AST test that scans `src/` (outside `runner.py`, `output.py`)       |
| P2  | Read-only is read-only  | `check_<x>`, `check.all`, `test.*`, `types.check`, `imports.*`, `security.audit` and `config.show` never change a tracked file. Their only writes are caches and the coverage reports.                                            | **new:** integration test: run them on a git probe project and require an empty `git status --porcelain`                 |
| P3  | Mutation is declared    | A task that changes files, the environment or a remote is named `fix_*`, or is a verb (`publish`, `build`, `install`, `clean`), and is marked in the README table.                                                                | `test_init.py` (names, summaries, options); **new:** README table compared with the task list                            |
| P4  | Exit codes              | `0` pass, or nothing to do (a `⏭️` line says why); `1` the checked thing failed; `2` invalid usage or config; `127` a tool or module is missing. The failure line is `❌ Failed: <what>` on stderr.                               | `Exit` raised in `config/_resolve.py`, `runner.py`, `tools.py`, `_steps.py`; **new:** one parametrized test of the table |
| P5  | Fail before acting      | An unknown key, an invalid value or a wrong working directory exits with `2` before any command runs. The message names the key.                                                                                                  | `config/_validate.py`, `_check_project_root`; `tests/unit/config/`                                                       |
| P6  | Missing tools           | A missing program or Python module is reported with the command that installs it. A composite task reports all the missing tools of its steps at once, and runs nothing.                                                          | `tools.hint`, `_steps.preflight_message`; `tests/unit/test_check.py`                                                     |
| P7  | Commands are data       | A task builds one command string from (config, options). Every user value is quoted: a space, `;`, `*`, `~` or `$VAR` reaches the tool unchanged.                                                                                 | `runner.build_command`; `tests/integration/test_quoting.py`; `_commands(c) == [...]` in unit tests                       |
| P8  | One source of truth     | A config key is declared once (`SCHEMA`), a tool once (`TOOLS`), a step once (`STEPS`), a directory policy once (`_files`). Defaults, the JSON schema, the hints and the docs tables derive from them.                            | tests that compare the tables; **new:** no derived table is kept (F3, F4)                                                |
| P9  | Safe by default         | A destructive task stays inside the project, keeps what git tracks, and asks before an irreversible step. A credential never appears in a command line or in the output.                                                          | `clean._is_inside_project`, `release._check_release_state`, `_publish_environment`; `tests/unit/test_release.py`         |
| P10 | Skips are visible       | A task that has nothing to do prints `⏭️ <reason>` and exits `0`. A task that cannot do its job (a path it needs is missing) exits non-zero and names the key. See section 3.5.                                                   | partly (F6); **new:** one test per rule                                                                                  |
| M1  | Layers                  | A task module imports only the support modules, never another task module. The two composites (`check`, `fix`) import task modules and `_steps`. `config`, `tools` and `output` import nothing of the package that is above them. | **new:** layering test that dogfoods `_graph.import_graph` on the package                                                |
| M2  | Public means documented | A name is public only if it is in the `__all__` of its module and in the user guide. Everything else starts with `_`.                                                                                                             | **new:** test that compares `__all__` with `uguide/custom_tasks.md`                                                      |
| M3  | Every function tested   | Every function, private ones included, has a docstring, a unit test and, if the unit test patches a collaborator, an integration test. Coverage is 100% (lines and branches).                                                     | `test_docstrings.py`, `--cov-fail-under=100`, `CLAUDE.md`                                                                |
| M4  | Cheap to import         | `import invoke_tasklib` stays below 100 ms; `make_ns()` does no I/O.                                                                                                                                                              | `tests/benchmarks/test_init_benchmark.py`, nightly `ci-benchmark.yaml`                                                   |

**Not guaranteed, and documented as such:**

- **Windows.** The tasks need a POSIX shell for the quoting. `make_ns` warns; nothing else is done.
  Supporting it would double the quoting code for a platform that the tools (`shellcheck`, `shfmt`)
  hardly support.
- **A skipped step is not a checked step.** `check.all` prints `⏭️` for the `unit` step of a
  project without `tests/unit`, then `✅ All checks passed`. This is P10 working as designed; the
  cost is that a typo in `paths.unit_tests` is a skip, not an error. The alternative is in D5.
- **Private Invoke attributes.** `config.show` and `_check_project_root` read ten private
  attributes of `invoke.config.Config` (`_defaults`, `_project_prefix`, ...). `invoke>=3.0,<4.0`
  allows every 3.x. The code warns when one is missing (`RuntimeWarning`, `⚠️` in `config.show`);
  it cannot do better because Invoke has no public API for them.
- **Tool versions.** `ty` is `0.x`. A new release can add errors to every downstream `check.all`.
  The checker is configurable (`tasklib.types.checker`), which is the whole mitigation.
- **Stale installs.** `imports.check-isolated` and `release.build` test what is installed. They are
  right to; they say so in their docstrings.

## 2. What differs today

| #   | Finding                                                                                                                                                                                                                                                                                                                                           | Status                                       |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| F1  | **Three exclusion lists and a half-dead parameter.** `config.EXCLUDED_DIRS` (not a config value), `formatting.SHELL_EXCLUDED_DIRS`, `testing.MARKDOWN_EXCLUDED_DIRS`. In a git work tree `project_files` ignores its `excluded` argument, so the two task lists apply only outside git: a tracked `build/run.sh` and `site/index.md` are checked. | [verified] (probe) + [reading]               |
| F2  | **`check.all` and `fix.all` are the same function written twice.** About 35 lines each: parse `--only`/`--skip`, select, find the blocked steps, call `run_steps`. `CLAUDE.md` tells agents that a change to one "usually needs the same change" in the other.                                                                                    | [reading]                                    |
| F3  | **`tools.py` derives three dicts from `TOOLS` and `env` two tuples.** `PROGRAM_HINTS`, `PROGRAM_GROUPS`, `MODULE_GROUPS` and `env.TOOL_PROGRAMS`/`TOOL_MODULES` only re-index `TOOLS`; `hint()` does two lookups in them. Tool names are unique across kinds, so one lookup in `TOOLS` is enough.                                                 | [reading]                                    |
| F4  | **The list of config sections is written in six places.** The dataclasses, `TasklibConfig`, `_SECTION_CLASSES`, seven `DEFAULT_*` dicts, the `sections` dict inside `default_config`, and `CHECK_STEPS`/`FIX_STEPS` next to `check.STEPS`/`fix.STEPS`. `config.__all__` exports 33 names, among them constants that are not config.               | [reading]                                    |
| F5  | **`imports.check-cycles` does not use `paths.src`.** It finds the package with the import machinery. In a project with `src/foo` and `paths.src` at its default, it fails with `No module named 'foo'` when `foo` is not installed; with a non-editable install it analyses the installed copy, not the source.                                   | [verified] (failure); [reading] (stale copy) |
| F6  | **No rule for a missing path.** `test.unit/integration/functional` skip (`⏭️`, exit 0); `test.benchmark` exits 1; `doc.*` exits 2 naming the key; `test.doctest-src` on a missing `paths.src` runs pytest and fails with `no tests ran`, naming nothing.                                                                                          | [verified]                                   |
| F7  | **`clean` imports `testing`, and `pyproject.toml` is read twice with two policies.** `clean` needs `coverage_outputs`, the only dependency between two task modules besides the composites. `testing._coverage_option` swallows a `TOMLDecodeError`; `release._project_version` turns it into an `Exit`.                                          | [reading]                                    |
| F8  | **Three version helpers and two regexes in `doc.py`.** `_parse_release`, `_release_key` and `_version_key` each parse a tag; `_version_key` has its own regex.                                                                                                                                                                                    | [reading]                                    |
| F9  | **The public surface is undefined.** `uguide/custom_tasks.md` lists 12 "supported public" helpers. `runner`, `tools`, `output` and `config` expose 33 public functions and classes (and the constants), all rendered in `docs/refs/` (for example `tools.PROGRAM_HINTS`, `config.Unset`, `runner.split_args`). Each is a promise.                 | [reading]                                    |
| F10 | **P1, P2 and M1 have no test.** Nothing scans `src/` for `c.run`/`print`, nothing checks the layers, and no integration test checks `git status` after the read-only tasks.                                                                                                                                                                       | [verified] (`grep` of `tests/`)              |
| F11 | **`main` is not clean under its own pinned linter.** `ruff check`: `_discover.py:186` D202 and `imports.py:68` W505 (doc line 73 > 72). `ruff format --check`: 5 files (the first two: `imports.py:23`, `lint.py:20`). `CLAUDE.md` asks for both to be clean.                                                                                     | [verified]                                   |
| F12 | **Test helpers are copied.** `_context` is defined in 8 unit modules next to `tests/helpers.make_context`.                                                                                                                                                                                                                                        | [verified] (`grep`)                          |

**Already correct, and must not regress.** The strict config (unknown key with a suggestion, `null`
rejected for an integer, the working-directory guard), the quoting, the exit-code convention, the
preflight of the tools of a composite and `--keep-going`, the ASCII fallback of the messages,
`release.build` verifying the artifact with `python -I`, the scrubbed credentials of `uv publish`,
`clean` refusing paths outside the project and tracked directories, the single `step` helper used
by every task, 100% coverage, the benchmarks that exist now, `docs-deps` installed in one cell of
`ci-test`, and `check.all --keep-going` as a pull-request job.

## 3. Architecture

### 3.1 Layers

```text
tasks.py:  ns = make_ns()                                   (the only public entry point)
               │
   L5   __init__.py ── make_ns: one Collection per module, NAMESPACE of each module
               │
   L4   check.py   fix.py                      composites: run STEPS with _steps.run_composite
               │
   L3   formatting lint typecheck testing env release doc security imports clean show
               │         task modules: @task functions; never import each other
               ▼
   L2   _steps   _files   _coverage   _pyproject   _graph        private helpers of tasks
               │
   L1   config/   runner   tools   output                 support: the documented helpers
               │
   L0   (stdlib, invoke)       _discover.py runs in a subprocess and imports nothing above
```

The rules (property M1): a module imports only from its own layer or the ones below it, and
within L3 not at all. `release.publish` calling `release.build` is the same module. Today there
is one violation, `clean -> testing`, and one inversion, `_graph -> _discover` (an L2 helper that
shares a function with the L0 worker; it is fine, both are private, and the test lists it as an
allowed edge).

### 3.2 Config

```python
# config/_schema.py
SCHEMA: dict[str, dict[str, Option]]   # section -> key -> Option(default, validate, json_schema, doc)

@dataclass(frozen=True)
class PackageConfig: ...               # one frozen dataclass per section (static typing, kept)
class TasklibConfig: package: PackageConfig; paths: PathsConfig; ...

def get_config(c) -> TasklibConfig     # raises ValueError
def load_config(c) -> TasklibConfig    # exits with 2 (P5)
def default_config() -> dict           # built by a loop over SCHEMA
def json_schema() -> dict              # built by a loop over SCHEMA
```

- The sections are written once, in `SCHEMA`, and once as dataclasses. The dataclasses stay: the
  static type of `cfg.paths.src` is the reason for them (`architecture.md`, "Why frozen
  dataclasses"), and `test_schema_keys_are_the_fields_of_the_section_dataclass` keeps the two
  aligned. Everything else is a loop over `SCHEMA`: `default_config`, `_SECTION_CLASSES` (looked
  up by name from the dataclasses), the JSON schema, the `config.show` rendering. The seven
  `DEFAULT_*` dicts go away (F4).
- `_validate_check_tasks` and `_validate_fix_tasks` become one `_validate_steps(valid, key)`
  partial.
- `Unset` and `default_config` stay: they are the price of the `INVOKE_TASKLIB_*` environment
  variables with Invoke's type casting, and they are tested (`unit_timeout: ~` is an error).
- `config/__init__.py` exports what a downstream project or task needs: `get_config`,
  `load_config`, `TasklibConfig` and the section dataclasses, `SCHEMA`, `Option`, `json_schema`,
  `default_config`. The constants (`COV_REPORTS`, `PYTHON_VERSION_PATTERN`, `CHECK_STEPS`,
  `FIX_STEPS`, `EXCLUDED_DIRS`) are imported from their private module by the code that needs
  them, and `EXCLUDED_DIRS` moves to `_files`, where it is used.

### 3.3 Tools and steps

```python
# tools.py: one record per program or module, one dict
TOOLS: dict[str, Tool]  # names are unique across kinds (a test asserts it)


def hint(name: str) -> str:  # one lookup
    tool = TOOLS.get(name)
    if tool is None:
        return DEFAULT_HINT
    if tool.hint:
        return tool.hint
    if tool.group:
        return f"Install it with the '{tool.group}' group: `uv sync --group {tool.group}`."
    return DEFAULT_HINT
```

`hint(name, module=...)` loses its `module` flag (the kind is in the record). `PLUGIN_OPTIONS` is
kept: it is a real inverse index (option to plugin), and `_check_plugin_options` reads it. The
other three derived dicts and `env.TOOL_PROGRAMS`/`TOOL_MODULES` are deleted; `env.check-tools`
loops over `TOOLS` (F3).

```python
# _steps.py
class Step(NamedTuple):
    task: Callable[[Context], None]
    programs: tuple[str, ...] | Callable[[TasklibConfig], tuple[str, ...]] = ()
    modules: tuple[str, ...] | Callable[[TasklibConfig], tuple[str, ...]] = ()

    def needs(
        self, cfg
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:  # replaces step_programs/step_modules
        ...


def run_composite(
    c,
    steps: Mapping[str, Step],
    valid: tuple[str, ...],
    configured: tuple[str, ...],
    *,
    only,
    skip,
    keep_going,
    label,
    messages,
) -> None:
    """parse --only/--skip, select, preflight (programs + modules), run_steps."""
```

`check.all_` and `fix.all_` each become a `load_config` and one `run_composite` call (about 10
lines each). A fix step has no modules, so the same preflight serves both (F2). `CHECK_STEPS` and
`FIX_STEPS` stay in `config/_constants.py` because `config` cannot import the task modules; the
test that compares them with `STEPS` stays (D4).

### 3.4 File selection

```python
# _files.py
EXCLUDED_DIRS: frozenset[str]   # .git .venv node_modules build dist site htmlcov and the tool caches

def project_files(c, root, suffix) -> list[Path]:
    # in a git work tree: git ls-files --cached --others --exclude-standard (.gitignore is the policy),
    #   minus the paths under .git/.venv/node_modules
    # otherwise: os.walk skipping EXCLUDED_DIRS
```

One list, one signature, no per-task constant (F1). Behaviour in a git work tree does not change
(it is the documented policy); outside git the shell and markdown tasks skip the same directories
as today, since the list is the union of the three. `clean._find_pycache_dirs` uses the same list:
a `__pycache__` inside `build/` or `site/` is removed with its parent, or kept with it when git
tracks files there.

### 3.5 Missing paths (property P10)

One rule, written in the docstring of `_files` and in the user guide:

| Kind of path                                                               | Missing                                               | Examples                                                                       |
| -------------------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------ |
| A directory the task may legitimately not have                             | `⏭️ No 'x' directory: skipping ...`, exit `0`         | `paths.unit_tests`, `integration_tests`, `functional_tests`, shell scripts     |
| A path the task is about                                                   | exit `2`, message names the key (`tasklib.paths.src`) | `paths.src` for `test.doctest-src`, `format.*-docstrings`; `paths.docs_config` |
| A directory that is the only input, in a task run to produce a measurement | exit `1`, as today                                    | `test.benchmark`                                                               |

A path given with `--paths` is never checked by the task: the tool reports it.

A helper `require_path(path, key)` in `_files.py` raises the `Exit(2)`; `doc._docs_config`,
`doctest_src` and the docstring tasks call it. This is the whole change for F6.

### 3.6 Imports

`imports.check-cycles` reads the sources of the package from `paths.src` (a static analysis needs
no import), and falls back to the import machinery only when the directory is absent. The message
of the fallback says `not found in 'src/foo' (tasklib.paths.src) and not installed`. The graph
code does not change: `_graph.read_sources(name, src=...)` gets an optional directory.
`imports.check-isolated` keeps testing the installed package, by design.

### 3.7 Shared readers and the composite of version helpers

- `_pyproject.py`: `read_pyproject(path=Path("pyproject.toml")) -> dict` returns `{}` for a missing
  file and raises `Exit(1)` naming the file for invalid TOML. One policy, used by `release`
  (`[project] version`) and `_coverage`. `clean` stays best-effort, as it already is for the
  config (`_cov_reports` catches `Exit`).
- `_coverage.py`: `CoverageOutputs`, `coverage_outputs`, and the helpers that read
  `[tool.coverage.*]` and `--cov-report` arguments (about 100 lines today in `testing.py`). Both
  `testing` and `clean` import it (F7).
- `doc.py`: one `_Version(NamedTuple)` with `major`, `minor`, `patch` and `prerelease`, and
  `_parse_version(text)`. `_release_key` is `(v.major, v.minor)`, `_version_key` is the tuple, and
  `_last_version_tag` is `max(...)` (F8).

### 3.8 Public API

After the change the public names are the ones the user guide documents (property M2):

```text
invoke_tasklib            make_ns, __version__, and the task modules (check, clean, doc, env, fix,
                          formatting, imports, lint, release, security, show, testing, typecheck)
invoke_tasklib.config     get_config, load_config, json_schema, default_config, SCHEMA, Option,
                          TasklibConfig and the section dataclasses
invoke_tasklib.runner     run, capture, build_command, split_args, python_executable, in_ci,
                          in_github_actions, ARGS_HELP, PATHS_HELP
invoke_tasklib.tools      check_program, find_tool, hint, not_found_message, tool_path, Tool, TOOLS
invoke_tasklib.output     say, step, report_failure
```

Everything else is private: `_steps`, `_files`, `_graph`, `_discover`, `_coverage`, `_pyproject`
and the names removed in section 4. The task modules keep their tasks, `NAMESPACE`, and the
constants of their tasks that the user guide mentions (`clean.DIRS`, ...).

### 3.9 Data flow

The flow does not change (`architecture.md` has the diagram): `inv` loads `invoke.yaml`, the task
calls `load_config(c)`, builds one command with `build_command`, and `runner.run` checks the
program, echoes the command and runs it. A composite replaces the last two lines with
`run_composite`, which checks all the tools first and then calls the tasks of its steps.

## 4. Rebuild rules and public API

- **Deletions** (breaking, listed in the `0.1.0` notes): `tools.PROGRAM_HINTS`,
  `PROGRAM_GROUPS`, `MODULE_GROUPS`, `DEFAULT_HINT` stays; `env.TOOL_PROGRAMS`, `TOOL_MODULES`;
  `config.DEFAULT_PACKAGE/PATHS/GROUPS/TEST/TYPES/CHECK/FIX`, `config.EXCLUDED_DIRS`,
  `COV_REPORTS`, `PYTHON_VERSION_PATTERN`, `CHECK_STEPS`, `FIX_STEPS`, `PROJECT_PREFIX_ATTRIBUTE`,
  `Unset`, `main` from the `config` namespace (they stay importable from their private modules);
  `formatting.SHELL_EXCLUDED_DIRS`, `testing.MARKDOWN_EXCLUDED_DIRS`; `testing.coverage_outputs`
  and `CoverageOutputs` (moved to `_coverage`); `check._missing_tools`; the `excluded` argument of
  `_files.project_files` and `find_files`.
- **Signature changes**: `tools.hint(name)` without `module=`; `_graph.read_sources(name, src=None)`.
- **Behaviour changes**: `imports.check-cycles` analyses `paths.src` first (F5);
  `test.doctest-src` and the docstring tasks exit `2` with the key name when `paths.src` is
  missing (F6). No task name, option or `invoke.yaml` key changes.
- **Rules for a new task** (unchanged, now complete): put it in the layer of section 3.1; read the
  config with `load_config`; build the command with `build_command`; run it with `run`; report
  with `step`; apply the missing-path table of section 3.5; list it in `_MODULES` through its
  module's `NAMESPACE`; update the five documentation places of `CLAUDE.md`.

## 5. Dependents

| Dependent                                                                                              | Change                                                                                                                                                                                                                                           |
| ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| A project with `make_ns()` and `invoke.yaml`                                                           | None. Same tasks, options and keys. `imports.check-cycles` now works from the source tree without an install; `test.doctest-src` names `paths.src` when it is wrong.                                                                             |
| A project with custom tasks                                                                            | None if it uses the 12 helpers of `custom_tasks.md`. It breaks if it imported `tools.PROGRAM_HINTS`, `config.DEFAULT_*`, `config.EXCLUDED_DIRS` or `testing.coverage_outputs`.                                                                   |
| This repository's workflows                                                                            | None: they call `inv` task names. `ci-check.yaml` already runs `check.all --keep-going`.                                                                                                                                                         |
| `README.md`, `docs/docs/uguide/`, `docs/docs/refs/`, `docs/docs/dev/architecture.md`, `development.md` | The README table does not change. `architecture.md` gets the properties and the layers; `development.md` gets the new modules in its tree; `refs/` loses the removed names; `uguide/index.md` and the namespace pages get the missing-path rule. |
| `CLAUDE.md`                                                                                            | The module list gains `_coverage.py` and `_pyproject.py`; the sentence "a change to the steps of `check.all` usually needs the same change in `fix.all`" is deleted (F2).                                                                        |
| `tests/`                                                                                               | New: `tests/unit/test_architecture.py`, tests of the three new private modules, integration tests for P2, F5 and F6. Moved: the coverage-output tests follow `_coverage`.                                                                        |

## 6. Evidence

Probes ran with the repository's `inv` in a throwaway project (`pyproject.toml`, `src/foo`,
`invoke.yaml` with `package.name: foo`, a git repository for the file probes). The "Target"
column is the behaviour that this plan specifies; it was not prototyped.

| Input                                                                  | Today [verified]                                                        | Target                                                 |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------ |
| `inv format.check-shell` with tracked `build/run.sh` in git            | checks `build/run.sh` (the constant says "never checked")               | same, and the constant is gone (git is the policy)     |
| `inv test.doctest-markdown` with tracked `site/index.md` in git        | checks `site/index.md`                                                  | same                                                   |
| `inv check --only imports` with `src/foo` present, `foo` not installed | `No module named 'foo'`, exit 1                                         | analyses `src/foo`, exit 0                             |
| `inv test.doctest-src` with no `src/`                                  | pytest `no tests ran`, `❌ Failed: Running doctests on source code`     | `'src/foo' (tasklib.paths.src) does not exist`, exit 2 |
| `inv test.unit` with no `tests/unit`                                   | `⏭️ No 'tests/unit' directory: skipping unit tests`, exit 0             | same (P10)                                             |
| `inv test.benchmark` with no `tests/benchmarks`                        | `No 'tests/benchmarks' directory: ...`, exit 1                          | same (documented in the rule table)                    |
| `inv doc.build` with no `docs/mkdocs.yml`                              | names `tasklib.paths.docs_config`, exit 2                               | same                                                   |
| `unit_timeout: ~` in `invoke.yaml`                                     | `'tasklib.test.unit_timeout' must be an integer >= 1, got None`, exit 2 | same (must not regress)                                |
| `tests:` (a typo for `test:`) under `tasklib`                          | `Unknown key 'tests' (did you mean 'test'?) ...`, exit 2                | same                                                   |
| `inv --list` / `import invoke_tasklib`                                 | 0.09 s / 60 ms                                                          | not slower (M4)                                        |
| `ruff check src tests`, `ruff format --check src tests`                | 2 errors, 5 files to reformat                                           | clean                                                  |

What this says: the package behaves well on the cases that earlier reviews fixed. The remaining
defects are about _where the code is looked for_ (F5, F6) and about rules that are true by habit
and not by test (F10). None of the target behaviours is a new capability; each one removes a
special case.

## 7. Changes to reach the target state

One branch and one pull request per row, as in `CLAUDE.md`. "Breaking" means a public name or a
behaviour changes (section 4). Rows that touch the same files are stacked in the order given;
the others branch from `main`.

| Step | Change                                                                                                                                                                                                                                                                                                                                                                 | Breaking                               |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| 1    | **Make `main` clean (F11).** `ruff check --fix` for D202, rewrap the W505 docstring, `ruff format`. Check `git stash` first, as `CLAUDE.md` says: these are failures of `main`.                                                                                                                                                                                        | no                                     |
| 2    | **Write the contract (F10).** Properties and layers into `architecture.md`; `tests/unit/test_architecture.py` with the P1 scan, the M1 layering (allowed edges listed, `clean -> testing` marked as the one known exception that step 4 removes), the tool-name uniqueness; integration test for P2 (`git status` after the read-only tasks); the exit-code test (P4). | no                                     |
| 3    | **`_pyproject.py` and `_coverage.py` (F7).** Extract, make `release` and `_coverage` use `read_pyproject`, `clean` and `testing` import `_coverage`. Remove the known exception of step 2.                                                                                                                                                                             | yes (`testing.coverage_outputs` moves) |
| 4    | **One exclusion list (F1).** `EXCLUDED_DIRS` into `_files`; delete the two per-task lists and the `excluded` argument; update the docstrings and `architecture.md`. Stacked on 3 (same files).                                                                                                                                                                         | yes (three constants removed)          |
| 5    | **`run_composite` (F2).** Add to `_steps`, shrink `check.all_` and `fix.all_`, `Step.needs` replaces `step_programs`/`step_modules`; delete the sentence in `CLAUDE.md`.                                                                                                                                                                                               | no (private)                           |
| 6    | **`hint` over `TOOLS` (F3).** Delete the three derived dicts and the two `env` tuples; `env.check-tools` loops over `TOOLS`.                                                                                                                                                                                                                                           | yes                                    |
| 7    | **Config from `SCHEMA` (F4).** Loop-built `default_config`, delete the `DEFAULT_*` dicts, merge the two steps validators, narrow `config.__all__`.                                                                                                                                                                                                                     | yes                                    |
| 8    | **`paths.src` for `imports.check-cycles` (F5).** `read_sources(name, src=...)`, fallback to the import machinery, new message, integration test on the probe project.                                                                                                                                                                                                  | behaviour                              |
| 9    | **The missing-path rule (F6).** `require_path`, used by `doctest_src`, the docstring tasks and `_docs_config`; the table of section 3.5 in the user guide.                                                                                                                                                                                                             | behaviour                              |
| 10   | **One version parser (F8).** `_Version` in `doc.py`; delete `_release_key`, `_version_key`. Same tests, fewer helpers.                                                                                                                                                                                                                                                 | no (private)                           |
| 11   | **Define the public API (F9).** `__all__` in `runner`, `tools`, `output`, `config`; prefix the rest with `_`; trim `docs/refs/`; the `__all__` against `custom_tasks.md` test of M2. Last of the breaking steps.                                                                                                                                                       | yes                                    |
| 12   | **Tidy the tests (F12).** `_context = partial(make_context, ...)` in the 8 modules; no behaviour change. Can run at any time.                                                                                                                                                                                                                                          | no                                     |
| 13   | **Release `0.1.0`.** Notes list the breaking rows (3, 4, 6, 7, 8, 9, 11) with the replacement for each name.                                                                                                                                                                                                                                                           | —                                      |

Order: 1 and 2 first (they fix the baseline and add the guards that protect the others). 3 then 4. 5, 6, 7 are independent of each other. 8 and 9 follow 4 (they use the new `_files`). 10 and 12
are free. 11 comes after 6 and 7, which remove the names it would otherwise have to make private.
Update the changelog or status table with the pull request number in each step.

## 8. Tests and gates

- **Architecture (`tests/unit/test_architecture.py`, new).** One AST scan: no `c.run(`, `print(`
  or `c.config` outside `runner.py`, `output.py` and `config/` (P1). One layering test built on
  `_graph.import_graph` over the package itself: the dict of layers is in the test, a violation
  fails with the edge (`clean -> testing`). One test that every `Tool` name is unique, and that
  every program and module named in `check.STEPS` and `fix.STEPS` is in `TOOLS`.
- **Step runner.** `run_composite` is tested once, with the cases now spread over `test_check.py`
  and `test_fix.py`: `--only`, `--skip`, unknown name, missing tool listed once, `--keep-going`,
  summary. `test_check.py` and `test_fix.py` keep only what is specific (the steps, the messages,
  the `unit` modules). Assert the whole list of commands (`_commands(c) == [...]`).
- **Config.** The existing schema tests stay. Add one that asserts `default_config()` equals the
  literal dict (the whole output, as `CLAUDE.md` asks), so the loop-built version is checked
  against what the hand-written one returned.
- **Files.** `project_files` in a git probe: tracked `build/x.sh` is returned; in a plain tree
  `build/x.sh` is skipped. `find_files` without the `excluded` argument.
- **Imports.** Unit: `read_sources` with a directory, and the fallback message. Integration (real
  `inv`, no patch): the probe project, `src/foo` not installed, `imports.check-cycles` exits `0`;
  a cycle in `src/foo` exits `1`. Regression test for F5; check that it fails without the fix
  (`git stash push src`).
- **Missing paths.** One parametrized test per row of the table of section 3.5, with the exit code
  and the key name in the message; integration test for `test.doctest-src` without `src/` (F6).
- **Read-only (P2, integration).** A git probe project; run `format.check-python`,
  `lint.check-python`, `types.check`, `test.doctest`, `imports.check-cycles`, `config.show`;
  assert `git status --porcelain` is empty after each.
- **Exit codes (P4).** One parametrized test: invalid config → 2, missing tool → 127, failing
  check → 1, skipped directory → 0.
- **Doctests.** New private functions get a `pycon` example as `CLAUDE.md` asks; this review has
  none (examples are `text`, never `>>>`).
- **Patched behaviour.** Every unit test that patches `shutil.which`, `importlib.util.find_spec` or
  the environment keeps its integration counterpart; steps 3 and 8 add the ones for `_coverage`
  and the source directory.
- **Gates.** `ruff check`, `ruff format --check`, `ty check`, `pytest tests --cov` at 100%,
  `inv test.doctest`, `inv check.all --keep-going` and the nightly benchmark with
  `--benchmark-compare-fail=mean:50%`. Add `inv test.benchmark` numbers for `project_files` and
  `import invoke_tasklib` to the notes of step 4 and 7 (the benchmarks exist; read them before and
  after).

## 9. Decisions for the maintainers

**D1. Define the public API now (step 11).** _Recommended: yes, before `0.1.0`._ A name in
`docs/refs/` is a promise; 33 functions and classes, plus constants, is more than anyone intends to keep, and an alpha is the
cheap moment to say which ones. The alternative is to leave the surface as it is and treat
everything as public: no work now, but every later cleanup (this one included) is a breaking
change.

**D2. Keep the flat layout and the `NAMESPACE` constants.** _Recommended: keep._ Modules named
after the tool (`formatting`, `typecheck`, `testing`) and a `NAMESPACE` constant were chosen in
pull request 324. Renaming again to put the namespace in the module name (`format_`, `types_`) trades one
workaround for another and breaks imports for no gain.

**D3. One exclusion list, git is the policy in a work tree (step 4).** _Recommended._ It keeps
the documented behaviour (`.gitignore` decides) and removes the dead code. The alternative is to
make the lists apply in git too: then a project that tracks scripts under `build/` stops having
them checked, which is a silent loss. If a project needs a custom exclusion, `--paths` is the
escape hatch; a config key is not worth adding.

**D4. Keep `CHECK_STEPS`/`FIX_STEPS` next to `STEPS`, guarded by a test.** _Recommended: keep._
`config` must not import the task modules (they import `config`), and the JSON schema enum gives
an editor completion of the step names. The alternative, validating the names at use time in
`check.all_`, removes the duplicate list but also the editor help and the early error (P5), and it
would be the first step toward downstream registration of steps (not covered, section 10).

**D5. Skipped steps stay green.** _Recommended: yes, as P10 says._ The alternative is to make a
missing `tests/unit` an error in `check.all` only (a `skip` becomes a failure when the step is
selected explicitly or is in `tasklib.check.tasks`). It catches a typo in `paths.unit_tests`, but
a project without functional tests then needs a way to say so, which is a new option. If the
typo case matters more than the extra option, add the check in `_unit` of `check.py` and nowhere
else.

**D6. `pyproject.toml` that does not parse is an error everywhere except `clean` (step 3).**
_Recommended._ Today `testing` returns the default silently and `release` stops. One policy is
easier to state; `clean` stays best-effort because it must work on a broken project.

**D7. Fix the `ruff` drift in step 1 or pin the lint version in CI.** _Recommended: fix it
(step 1)._ The lock file already pins `0.17.3`; the two errors and the five formatting
differences are in code, not in the version. If CI runs another `ruff`, the question is why, not
the code.

## 10. Not covered

- **Downstream registration of steps** (`make_ns(steps=...)`, a project adding its own step to
  `check.all`). It is the natural extension of `STEPS`, but it needs a public step API and a
  decision on D4; no project asks for it yet.
- **Windows support.** See section 1.
- **Other installers than `uv`.** `env.*`, `release.*` and `security.audit` call `uv`; the README
  says so.
- **Changing the tools** (ruff, ty, docformatter, codespell, mike). `types.checker` already
  covers the one that mattered.
- **`.make/`, `Makefile`, the workflows and `dev/`.** Not part of the package. The workflows need
  no change for this plan.
- **Machine-readable output** (`--json` for `check.all`). Useful, but a new feature.
- **Parallel steps.** The steps run in order on purpose (the fixes converge in order).
- **Rewriting the user guide.** Only the pages listed in section 5 change.

## Appendix A. Effect on package size

"Lines" is the length of the file; "code" is the number of non-blank lines once the docstrings are
removed (measured with `ast`). "After" is an estimate, not a measurement.

| Module                | Lines today | Code today | Expected after (lines) | Why                                                              |
| --------------------- | ----------: | ---------: | ---------------------: | ---------------------------------------------------------------- |
| `config/` (7 files)   |       1,610 |        304 |                  1,490 | `DEFAULT_*`, merged validator, narrower `__init__`, no constants |
| `tools.py`            |         466 |         86 |                    400 | three derived dicts and their docstrings                         |
| `_steps.py`           |         362 |         79 |                    390 | gains `run_composite`, loses two helpers                         |
| `check.py` + `fix.py` |         315 |         44 |                    230 | the shared selection moves to `_steps`                           |
| `testing.py`          |         627 |        139 |                    480 | coverage helpers move out                                        |
| `_coverage.py`        |           — |          — |                    170 | new (moved code, docstrings, tests move with it)                 |
| `_pyproject.py`       |           — |          — |                     50 | new                                                              |
| `_files.py`           |         137 |         29 |                    135 | no `excluded` argument, gains `require_path` and the list        |
| `formatting.py`       |         206 |         62 |                    190 | no per-task list                                                 |
| `doc.py`              |         411 |        103 |                    340 | one version parser                                               |
| `release.py`          |         420 |        125 |                    400 | uses `read_pyproject`                                            |
| `clean.py`            |         386 |        110 |                    375 | imports `_coverage`                                              |
| `env.py`              |         254 |        101 |                    245 | loops over `TOOLS`                                               |
| `imports.py`          |         138 |         50 |                    145 | passes `paths.src`                                               |
| `_graph.py`           |         483 |        157 |                    495 | `read_sources(name, src)`                                        |
| the rest              |       1,178 |          — |                  1,178 | unchanged                                                        |
| **Total**             |   **7,397** |            |             **~7,120** | about -4%; the unit tests shrink by about the same share         |

The saving is small on purpose: the package is already compact, and its length is mostly
docstrings and doctests that the project requires. The gain is the number of places a change must
touch: a new tool is edited in one place (`TOOLS`) and a new config section in two (`SCHEMA` and
its dataclass), and `check.all`/`fix.all` can no longer drift.

## Appendix B. How this was checked

- **Read:** every module of `src/invoke_tasklib/` (with `ast` to print the code without the
  docstrings), `pyproject.toml`, `CLAUDE.md`, `architecture.md`, `development.md`,
  `custom_tasks.md`, the README task table, `review/suggestions.md`, the `ci*.yaml` workflow
  headers and the `docs-deps` input.
- **Ran:** `pytest tests` (with coverage), `ruff check`, `ruff format --check`, `ty check`,
  `inv test.doctest`, `pytest -rs`; an import graph of the package from `ast` (the layering of
  section 3.1); probes in a throwaway project for F1, F5, F6 and the "must not regress" rows;
  `python -X importtime` and `time inv --list`.
- **Not run:** the target. No prototype exists, so section 6's "Target" column and Appendix A's
  "after" column are specifications and estimates. Findings marked **[reading]** (F2, F3, F4, F7,
  F8, F9) need a second look in the pull request of their step, as does the claim that no test
  covers P1/P2/M1 (a `grep` of `tests/`, not a review of the 2,964 tests).
