# `invoke_tasklib`: target state and the changes to reach it

This document proposes the target state of the `invoke_tasklib` package and the sequence of small
changes that gets there from `main` (`664deef`, `0.1.0a0`). It replaces the previous target state
(`3bb705b`), whose steps 1-12 are merged; the old text stays in the git history. It follows the
principles of the documentation (`docs/docs/dev/architecture.md`, `CLAUDE.md`, the user guide): one
config entry point, convention over configuration, composable tasks, no hidden state, a read-only
`check_<x>` for every mutating `fix_<x>`. Breaking changes are accepted (the package is an alpha),
and the future state weighs more than the past one.

The previous target state removed the duplicated tables and wrote the first half of the contract.
This one looks at what is left after that: places where the code does not say what the contract
says, a contract that is only partly written in the documentation, and a few repetitions that the
earlier cleanups exposed. The package is already compact; most of this document is about tightening
rules and deleting special cases, not about adding code. It adds no task, no dependency and no
option.

**Evidence labels.** **[verified]** means reproduced by running code (the repository's `.venv`
tools, or a throwaway project outside the repository). **[reading]** means found by reading the
source and not run.

**What was not changed.** No source file or test was changed to write this document. The probes ran
in a throwaway project in the scratchpad, outside the repository. `release.publish`,
`doc.publish-*` and the workflows were not run, and CI was not looked at.

**Baseline on `main`** [verified]: `pytest tests --cov` 3073 passed, 13 skipped (the skipped tests
are the `mike` ones: the `docs` group is not installed in this environment); coverage 100% (lines
and branches, `TOTAL 1708 0 432 0`); `ruff check src tests`, `ruff format --check src tests` and
`ty check` clean; `inv test.doctest` passes (47 markdown files). `import invoke_tasklib` takes 0.08 s
and `inv --list` 0.14 s (one run each, wall time).

## Constraints

1. **Simple and easy to maintain.** The only runtime dependency stays `invoke`. A change is accepted
   when it deletes more than it adds, or when it turns an unwritten rule into a test. No plug-in
   system, no new option, no new abstraction layer.
2. **Breaking changes are allowed, in one release.** The version is `0.1.0a0`. The breaking steps
   below ship together in `0.1.0` and are listed in its notes. The task names, the task options, the
   `make_ns` signature and the keys of `invoke.yaml` do not change, so a project's `tasks.py` and
   `invoke.yaml` keep working.
3. **Start-up cost is a floor.** `import invoke_tasklib` takes about 80 ms, 30 ms of them for
   `invoke.collection` [verified with `python -X importtime`]. The limit of M4 is 100 ms, so there
   is little room: nothing in the target may import more than today.
4. **One convention per concern**, as in `CLAUDE.md`: read the config with `load_config`, run a
   command with `runner.run`, print with `output.say`. A rule that has no test is not a rule
   (section 8).
5. **Match the surrounding code**: docstrings, naming, test style and the three-line section headers
   of the tests stay as they are.

## 1. Properties of the sub-package

These are the properties that the package guarantees to a project that uses it (`P1`-`P12`), then
those it guarantees to its own maintainers (`M1`-`M5`). The last column says where each one is
enforced today, or **new:** what this plan adds (section 8). `P11`, `P12` and `M5` are new; `P1`,
`M2` and `M3` are widened; the others are unchanged and are listed because the properties are only
a contract when all of them are written in one place. Today `architecture.md` lists 8 of the 17
(F1).

| #   | Property                | Statement                                                                                                                                                                                                                                               | Enforced by                                                                                                      |
| --- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| P1  | One entry point         | The config is read with `load_config`; a command runs through `runner.run` or `runner.capture`; a message goes through `output.say`, `step` or `report_failure`. The only environment variables read are the ones of section 3.7.                       | `test_architecture.py` (AST scan of `src/`); **new:** the scan also lists the readers of `os.environ`            |
| P2  | Read-only is read-only  | `check_<x>`, `check.all`, `test.*`, `types.check`, `imports.*`, `security.audit` and `config.show` never change a tracked file. Their only writes are caches and the coverage reports.                                                                  | `tests/integration/test_read_only.py`                                                                            |
| P3  | Mutation is declared    | A task that changes files, the environment or a remote is named `fix_*`, or is a verb (`publish`, `build`, `install`, `clean`), and is marked in the README table.                                                                                      | `test_init.py` (names, summaries, options); `tests/integration/test_readme.py`                                   |
| P4  | Exit codes              | `0` pass, or nothing to do (a `⏭️` line says why); `1` the checked thing failed; `2` invalid usage or config; `127` a tool or module is missing. The failure line is `❌ Failed: <what>` on stderr.                                                     | `tests/integration/test_exit_codes.py`                                                                           |
| P5  | Fail before acting      | An unknown key, an invalid value or a wrong working directory exits with `2` before any command runs. The message names the key.                                                                                                                        | `config/_validate.py`, `_check_project_root`; `tests/unit/config/`                                               |
| P6  | Missing tools           | A missing program or Python module is reported with the command that installs it. A composite task reports all the missing tools of its steps at once, and runs nothing.                                                                                | `tools.hint`, `_steps.preflight_message`; `tests/unit/test_check.py`                                             |
| P7  | Commands are data       | A task builds one command string from (config, options). Every user value is quoted: a space, `;`, `*`, `~` or `$VAR` reaches the tool unchanged.                                                                                                       | `runner.build_command`; `tests/integration/test_quoting.py`; `_commands(c) == [...]` in unit tests               |
| P8  | One source of truth     | A config key is declared once (`SCHEMA`), a tool once (`TOOLS`), a step once (`STEPS`), a directory policy once (`_files`). Defaults, the JSON schema, the hints and the docs tables derive from them.                                                  | tests that compare the tables; **new:** the directory lists of `clean` derive from `_files` (F6)                 |
| P9  | Safe by default         | A destructive task stays inside the project, keeps what git tracks, and asks before an irreversible step. A credential never appears in a command line or in the output.                                                                                | `clean._is_inside_project`, `release._check_release_state`, `_publish_environment`; `tests/unit/test_release.py` |
| P10 | Skips are visible       | A task that has nothing to do prints `⏭️ <reason>` and exits `0`. A task that cannot do its job (a path it needs is missing) exits non-zero and names the key (section 3.5 of the previous target state, now in the user guide).                        | `_files.require_path`; `tests/unit/test__files.py`, `tests/integration/test_files.py`                            |
| P11 | Fix converges           | After `fix_<x>` (or `fix.all`) the matching `check_<x>` (or `check.all --only` the same steps) passes, and a second `fix_<x>` changes nothing.                                                                                                          | **new:** integration test on a git probe project (F3)                                                            |
| P12 | Composition is explicit | `make_ns(include=, exclude=)` selects the tasks that the command line offers. The steps of `check.all` and `fix.all` come only from `tasklib.check.tasks` and `tasklib.fix.tasks`; excluding a task from the namespace does not remove its step.        | **new:** unit test of `make_ns` next to `check.all`; one sentence in `uguide/check.md` and `uguide/fix.md` (F2)  |
| M1  | Layers                  | A task module imports only the support modules, never another task module. The two composites (`check`, `fix`) import task modules and `_steps`. `config`, `tools` and `output` import nothing of the package that is above them.                       | `test_architecture.py` (layering test on `_graph.import_graph`)                                                  |
| M2  | Public means documented | A name is public only if it is in the `__all__` of its module and in the user guide. A task module has no public name except its tasks and `NAMESPACE`. Everything else starts with `_`.                                                                | `test_architecture.py` (`__all__` against `custom_tasks.md`); **new:** the same for the task modules (F5)        |
| M3  | Every function tested   | Every function, private ones included, has a docstring, a unit test and, if the unit test patches a collaborator, an integration test. Coverage is 100% (lines and branches). A function has no parameter that every caller passes with the same value. | `test_docstrings.py`, `--cov-fail-under=100`, `CLAUDE.md`; the last sentence is a review rule (F4)               |
| M4  | Cheap to import         | `import invoke_tasklib` stays below 100 ms; `make_ns()` does no I/O.                                                                                                                                                                                    | `tests/benchmarks/test_init_benchmark.py`, nightly `ci-benchmark.yaml`                                           |
| M5  | Invoke internals apart  | The private attributes of `invoke.config.Config` are read in one module, `config/_invoke.py`, which warns when one is missing. No other module calls `getattr` or `hasattr` on a config for a name that starts with `_`.                                | **new:** AST test over `src/` (F7)                                                                               |

**Not guaranteed, and documented as such:**

- **Windows.** The tasks need a POSIX shell for the quoting. `make_ns` warns; nothing else is done.
  Supporting it would double the quoting code for a platform that the tools (`shellcheck`, `shfmt`)
  hardly support.
- **A skipped step is not a checked step.** `check.all` prints `⏭️` for the `unit` step of a project
  without `tests/unit`, then `✅ All checks passed`. This is P10 working as designed (decision D5 of
  the previous target state): a typo in `paths.unit_tests` is a visible skip, not an error.
- **Private Invoke attributes.** `config.show` and the working-directory guard read ten private
  attributes of `invoke.config.Config`. `invoke>=3.0,<4.0` allows every 3.x. M5 keeps them in one
  module; the code warns when one is missing and cannot do better, because Invoke has no public API
  for them.
- **Tool versions.** `ty` is `0.x`. A new release can add errors to every downstream `check.all`.
  The checker is configurable (`tasklib.types.checker`), which is the whole mitigation.
- **Stale installs.** `imports.check-isolated` and `release.build` test what is installed. They are
  right to; they say so in their docstrings.
- **Reporting every cycle in the minimal way.** `imports.check-cycles` reports one cycle per
  strongly connected component, not every elementary cycle.

## 2. What differs today

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Status                          |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| F1  | **The contract is half written.** `architecture.md` has 8 properties (P1, P2, P4, P5, P7, M1, M2, M3). P3, P6, P8, P9, P10 and M4 exist only in `review/target_state.md`, which is a review and is replaced by every new one. The durable home of the contract is the architecture page.                                                                                                                                                                                                                                                                                                                               | [verified] (`grep` of the page) |
| F2  | **`make_ns(exclude=...)` does not reach the composites.** With `make_ns(exclude="lint")`, `inv --list` no longer offers `lint.*`, but `inv check --only lint` runs `ruff check` and fails on the code. `uguide/check.md` tells how to exclude the composite itself (`exclude=["check"]`), not that it ignores the other exclusions. The behaviour is reasonable; it is not stated and not tested.                                                                                                                                                                                                                      | [verified] (probe)              |
| F3  | **Nothing tests that a fix leads to a passing check.** The integration tests run `fix` tasks one by one, never `fix.all`, and never run the matching check afterwards. A `fix_python` whose result `check_python` rejects (different arguments, a changed default) is invisible.                                                                                                                                                                                                                                                                                                                                       | [verified] (`grep` of `tests/`) |
| F4  | **`testing._run_pytest` has two parameters that no caller varies.** `skip_missing` is `True` in the four callers (`all_`, `unit`, `integration`, `functional`), and `cfg` is passed by the four, so `cfg = cfg or load_config(c)` never loads. The function has 11 parameters. `_find_markdown_files` is a one-line wrapper of `project_files`.                                                                                                                                                                                                                                                                        | [verified] (`grep`) + [reading] |
| F5  | **The task modules expose 22 public names that are not tasks.** `clean.DIRS`, `DIR_GLOBS`, `FILES`, `FILE_GLOBS`, `SITE_DIR`, `MKDOCS_CONFIGS`; `env.PRE_COMMIT_CONFIG`, `VENV_DIR`, `LOCK_FILE`; `release.TWINE_REQUIREMENT`, `TEST_PYPI_PUBLISH_URL`, `TEST_PYPI_CHECK_URL`, `PUBLISH_CREDENTIAL_VARIABLES`; `testing.COV_HELP`, `APPEND_HELP`, `PYTEST_HELP`, `APPEND_PYTEST_HELP`; `typecheck.COMMANDS`; `security.PIP_AUDIT_REQUIREMENT`; `show.LEVELS`; `check.STEPS`, `fix.STEPS`. None is in the user guide, none has an `__all__`, and `docs/refs/` renders them. Each is a promise that M2 says nobody made. | [verified] (`grep`)             |
| F6  | **Two overlapping lists of directories.** `clean.DIRS` (11 names) and `_files.EXCLUDED_DIRS` (12 names) share 8 names (`build`, `dist`, `htmlcov`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.tox`, `.nox`), and `_files` itself keeps two sets (`_ENVIRONMENT_DIRS` and `_OUTPUT_DIRS`). A cache added to one list is forgotten in the other.                                                                                                                                                                                                                                                                   | [verified] (set comparison)     |
| F7  | **Private Invoke attributes are read in two places, and `show` reaches into the private modules of `config`.** `_resolve` reads `_project_prefix`; `show` reads nine other attributes through its own `LEVELS` tuple and imports `PROJECT_PREFIX_ATTRIBUTE` from `config._resolve` and `Unset` from `config._schema`, although `config.__all__` was narrowed to avoid exactly this.                                                                                                                                                                                                                                    | [verified] (`grep`) + [reading] |
| F8  | **`default_config` special-cases integers and keeps defaults that nothing uses.** `_untyped` returns an `Unset` for an `int` default (so a `bool` too) and the real default otherwise, to make Invoke cast an environment variable as a string. `get_config` merges the `SCHEMA` defaults again, and ignores `Unset`. A probe shows that an `Unset` for every key gives the same strings for every type.                                                                                                                                                                                                               | [verified] (probe, section 6)   |
| F9  | **The validators repeat the key path.** In `_schema.py` the section and the key are written in the `SCHEMA` position, again as arguments of `_path` or `_timeout`, and again in the `partial(_validate_..., "section", "key")` (10 `partial` calls). `_validate_str`, `_validate_int` and `_validate_bool` take `section` and `key` only to build the message. The resolver knows the path.                                                                                                                                                                                                                            | [reading]                       |
| F10 | **`clean` reads the config three times with the same `try/except Exit`.** `_cov_reports`, `_coverage_outputs` and `_site_dirs` each call `load_config` and catch the exit, because `clean` must work on a broken project. One best-effort read would do.                                                                                                                                                                                                                                                                                                                                                               | [reading]                       |
| F11 | **`release.py` parses `--args` twice, and mixes the order.** `_build_targets` splits `--args` with `shlex.split` (the rest of the package uses `split_args`, which turns a bad quote into an exit `2`) to find `--out-dir`, `--wheel` and `--sdist` of `uv build`. `TWINE_REQUIREMENT` and the URL constants sit between functions. `publish` is 45 lines: the credential lookup, the state checks, the confirmation and the command.                                                                                                                                                                                  | [reading]                       |
| F12 | **Stale comments.** The docstring of `check.STEPS` says "its tools to `env.py`"; the tools are in `tools.TOOLS` since the registry. `lint.NAMESPACE` and `imports.NAMESPACE` have no attribute docstring, unlike the 11 other task modules.                                                                                                                                                                                                                                                                                                                                                                            | [verified] (`grep`)             |

**Already correct, and must not regress.** The strict config (unknown key with a suggestion, `null`
rejected for an integer, the working-directory guard), the quoting, the exit-code convention, the
preflight of the tools of a composite and `--keep-going`, the ASCII fallback of the messages,
`release.build` verifying the artifact with `python -I`, the scrubbed credentials of `uv publish`,
`clean` refusing paths outside the project and tracked directories, the single `step` helper used by
every task, the missing-path rule and `require_path`, `imports.check-cycles` reading `paths.src`,
`run_composite` shared by `check.all` and `fix.all`, one `TOOLS` registry, one `_Version` in
`doc.py`, `__all__` in the support modules, 100% coverage, and the layering test.

## 3. Architecture

The layers do not change. They are the ones of the previous target state, enforced by
`test_architecture.py`.

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
   L2   _steps   _files   _coverage   _pyproject   _graph   private helpers of tasks
               │
   L1   config/   runner   tools   output                    support: the documented helpers
               │
   L0   (stdlib, invoke)       _discover.py runs in a subprocess and imports nothing above
```

### 3.1 The contract, in one place (F1, F2, F3)

The 17 properties of section 1 move into `docs/docs/dev/architecture.md`, in the table that exists
there, with the same three columns. The review keeps a pointer to them and no copy. A property that
is in the page and has no test is marked as such in the page, so a reader can tell a guarantee from
a wish. Two sentences are added to the user guide: in `uguide/check.md` and `uguide/fix.md`, "the
steps come from `tasklib.check.tasks`; `make_ns(exclude=...)` does not remove them" (P12).

```text
Property P11, as a test (tests/integration/test_fix_converges.py):
  project: git repo with a badly formatted file and an unsorted import
  run:     inv fix.all                        -> exit 0
  assert:  inv check --only format-python,lint -> exit 0
  assert:  git diff after a second `inv fix.all` equals the diff after the first
```

### 3.2 Config (F7, F8, F9)

```python
# config/_invoke.py  (new, about 60 lines: the only module that touches Invoke privates, M5)
LEVELS: tuple[tuple[str, str], ...]  # moved from show.py


def project_root(config) -> Path | None: ...  # was _resolve._check_project_root's read
def levels(config) -> Iterator[tuple[str, str, Mapping]]: ...  # for show._origin
def missing_internals(config) -> list[str]: ...  # for the warning of show and of load_config
```

- `_resolve._check_project_root` and `show` call these functions. `show` stops importing
  `config._resolve` and `config._schema`; `Unset` is read through `_invoke.is_unset` or stays in
  `_schema` and is imported by `_invoke` only (the test of M5 allows `_invoke` to import `_schema`).
- `default_config()` returns `{section: {key: Unset() for key in options}}`. `_untyped` goes away.
  Invoke only reads an environment variable for a key that exists in the defaults, and casts the
  variable like the existing value; an `Unset` is a `str`, so every value arrives as text and the
  validators parse it (`_validate_int`, `_validate_bool`, `_as_names` already do). The real defaults
  stay in `SCHEMA`, where `get_config` and the JSON schema read them.
- A validator is `Callable[[str, object], object]`: it receives the path
  `tasklib.<section>.<key>` and the value. `get_config` builds the path from the position in
  `SCHEMA` and passes it, so `partial(_validate_str, "paths", "src")` becomes `_validate_str`,
  `_path(...)` and `_timeout(...)` lose their key argument, and `_validate_int`/`_validate_bool`
  lose `section` and `key`. The messages do not change (the unit tests assert them).
- `main` (the JSON schema printer) moves from `_schema.py` to `__main__.py`, which is where the
  user guide says it lives.

### 3.3 Task modules (F4, F5, F10, F11, F12)

```python
# testing.py: the skip rule belongs to the function, the config is an argument
def _run_pytest(
    c, cfg, path, *, label, timeout, cov=False, append=False, args=None, paths=None
) -> None: ...  # 9 parameters, no skip_missing, cfg required
```

- Every module-level name of a task module that is not a task or `NAMESPACE` starts with `_`: the
  22 names of F5. `check.STEPS` and `fix.STEPS` become `_STEPS`; the architecture tests and
  `test_check.py` follow. The pytest help dicts of `testing` become `_PYTEST_HELP`. The user guide
  never mentioned them.
- `clean`: one `_try_config(c) -> TasklibConfig | None` (a `load_config` that returns `None` on an
  exit). `all_` calls it once and passes the result to the three helpers, which keep their best
  effort behaviour (a broken `invoke.yaml` or `pyproject.toml` does not stop `clean`).
- `release`: `_build_targets` uses `split_args`; the constants move to the top of the module;
  `publish` calls `_credentials(test_pypi) -> tuple[str, str | None, bool]` (the variable name, the
  token and whether trusted publishing applies), a pure function of the environment.
- The `check.STEPS` docstring says where a new tool goes (`tools.TOOLS`); `lint` and `imports` get
  the `NAMESPACE` docstring.

### 3.4 One list of directories (F6)

```python
# _files.py
CACHE_DIRS = frozenset(
    {
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        ".nox",
        ".hypothesis",
        ".benchmarks",
        ".coverage_html",
    }
)
OUTPUT_DIRS = frozenset({"build", "dist", "site", "htmlcov"})
ENVIRONMENT_DIRS = frozenset({".git", ".venv", "node_modules"})
EXCLUDED_DIRS = CACHE_DIRS | OUTPUT_DIRS | ENVIRONMENT_DIRS  # a walk never enters them
```

`clean.DIRS` becomes `tuple(sorted(CACHE_DIRS | {"build", "dist", "htmlcov"}))`: `site` and the
configured HTML directory are handled apart, as today. The git branch of `project_files` leaves out
`ENVIRONMENT_DIRS | CACHE_DIRS` (today `_ENVIRONMENT_DIRS`, which already holds the caches). The
walk now also skips `.hypothesis`, `.benchmarks` and `.coverage_html`, which hold no source file;
this is the whole behaviour change.

### 3.5 Data flow and public API

The flow does not change: `inv` loads `invoke.yaml`, the task calls `load_config(c)`, builds one
command with `build_command`, and `runner.run` checks the program, echoes the command and runs it. A
composite replaces the last two lines with `run_composite`. The public names after the change:

```text
invoke_tasklib            make_ns, __version__, and the task modules (check, clean, doc, env, fix,
                          formatting, imports, lint, release, security, show, testing, typecheck)
                          -- a task module exposes its tasks and NAMESPACE, nothing else
invoke_tasklib.config     get_config, load_config, json_schema, default_config, SCHEMA, Option,
                          TasklibConfig and the section dataclasses       (unchanged)
invoke_tasklib.runner     run, capture, build_command, split_args, python_executable, in_ci,
                          in_github_actions, ARGS_HELP, PATHS_HELP         (unchanged)
invoke_tasklib.tools      check_program, find_tool, hint, not_found_message, tool_path, Tool, TOOLS
                                                                           (unchanged)
invoke_tasklib.output     say, step, report_failure                        (unchanged)
```

### 3.6 Considered and not proposed

- **`graphlib` for the import cycles.** `graphlib.TopologicalSorter` raises `CycleError` with one
  cycle, so about 100 lines of `_Tarjan`, `_components` and `_cycle_in` could go. But the task
  reports every strongly connected component, and `graphlib` would stop at the first. Reporting all
  the cycles in one run is the useful behaviour; the code stays.
- **Splitting `testing.py` (469 lines).** The module holds the pytest suites, the two doctest tasks,
  the coverage report and the benchmark, all in the `test` namespace. Splitting it would add modules
  without removing code (D2 of the previous target state keeps one module per namespace).
- **Renaming `show.py` or its `config` namespace.** The module is `show` and its namespace is
  `config`, while `invoke_tasklib.config` is the package of the resolver. It is confusing in the
  source and invisible to the user (`inv config.show`). The previous decision (D2) stands: the
  command line name wins over the file name.

### 3.7 The environment variables the package reads

| Variable                                                 | Read in                  | For                                                         |
| -------------------------------------------------------- | ------------------------ | ----------------------------------------------------------- |
| `INVOKE_TASKLIB_<SECTION>_<KEY>`                         | Invoke, through `config` | Overrides a config key (the only config-like variable)      |
| `CI`, `GITHUB_ACTIONS`                                   | `runner`                 | `in_ci`, `in_github_actions`                                |
| `INVOKE_TASKLIB_ASCII`                                   | `output`                 | Forces ASCII messages; a display setting, not a project one |
| `PATH`                                                   | `tools`                  | `tool_path`                                                 |
| `PYPI_TOKEN`, `TEST_PYPI_TOKEN`, `UV_PUBLISH_TOKEN`, ... | `release`                | The credentials of `release.publish`, scrubbed for `uv`     |
| `ACTIONS_ID_TOKEN_REQUEST_URL`                           | `release`                | Detects trusted publishing                                  |

The AST test of P1 lists the readers of `os.environ` and compares them with this table, so a new
variable is a documented decision.

## 4. Rebuild rules and public API

- **Deletions and renames** (breaking, listed in the `0.1.0` notes): the 22 names of F5 (they start
  with `_` after the change); `config.show.LEVELS` (moves to `config/_invoke.py`);
  `config._schema._untyped`, `_path`'s and `_timeout`'s key argument, the `section` and `key`
  arguments of the validators (private); `testing._find_markdown_files`;
  `testing._run_pytest`'s `skip_missing` and optional `cfg`.
- **Signature changes**: none public. `default_config()` returns an `Unset` for every key (its
  keys do not change); a project that read `c.config.tasklib.test.unit_timeout` directly got `10`
  and now gets an empty `Unset`. The user guide says to use `load_config`, and `config.show` prints
  the resolved value.
- **Behaviour changes**: the walk of the file tree skips three more cache directories (3.4). No task
  name, option or `invoke.yaml` key changes.
- **Rules for a new task** (unchanged, now complete): put it in the layer of section 3; read the
  config with `load_config`; build the command with `build_command`; run it with `run`; report with
  `step`; apply the missing-path table of the user guide; keep every other name of the module
  private; list the module in `_MODULES` through its `NAMESPACE`; update the five documentation
  places of `CLAUDE.md`.

## 5. Dependents

| Dependent                                                                                              | Change                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A project with `make_ns()` and `invoke.yaml`                                                           | None. Same tasks, options and keys.                                                                                                                                                                                                    |
| A project with custom tasks                                                                            | None if it uses the 12 helpers of `custom_tasks.md`. It breaks if it imported a constant of a task module (`clean.DIRS`, `testing.PYTEST_HELP`, `check.STEPS`, ...) or read `c.config.tasklib` for a default.                          |
| This repository's workflows                                                                            | None: they call `inv` task names.                                                                                                                                                                                                      |
| `README.md`, `docs/docs/uguide/`, `docs/docs/refs/`, `docs/docs/dev/architecture.md`, `development.md` | `architecture.md` gets the 17 properties and `config/_invoke.py`; `development.md` gets the new module in its tree; `uguide/check.md` and `fix.md` get the P12 sentence; `refs/` loses the 22 names; the README table does not change. |
| `CLAUDE.md`                                                                                            | The module list gains `config/_invoke.py`; the "Code" section says a task module has no public name but its tasks and `NAMESPACE`.                                                                                                     |
| `tests/`                                                                                               | New: `tests/integration/test_fix_converges.py`, the `os.environ` and `_invoke` scans in `test_architecture.py`, a `make_ns` test for P12, tests of `_invoke`, `_try_config` and `_credentials`.                                        |

## 6. Evidence

Probes ran with the repository's `inv` and `.venv` in a throwaway project (`pyproject.toml`,
`src/foo`, `invoke.yaml` with `package.name: foo`, a git repository). The "Target" column is the
behaviour that this plan specifies; it was not prototyped, except the `Unset` row.

| Input                                                                                                                                                               | Today [verified]                                                                       | Target                                |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------- |
| `make_ns(exclude="lint")`, then `inv --list`                                                                                                                        | no `lint.*` task is offered                                                            | same (P12)                            |
| the same project, `inv check --only lint`                                                                                                                           | runs `ruff check`, prints `❌ Failed: Checking code linting with ruff`                 | same, and the page says so (P12)      |
| `Config(defaults={"tasklib": {s: {k: Unset()}}})` with `INVOKE_TASKLIB_TEST_XDOCTEST=false`, `_UNIT_TIMEOUT=5`, `_COV_FAIL_UNDER=90`, `INVOKE_TASKLIB_CHECK_COV=no` | the values are `'false'`, `'5'`, `'90'`, `'no'`, all `str`; the validators accept them | `default_config()` is this dict (F8)  |
| `grep -rn "fix.all" tests/integration`                                                                                                                              | no match                                                                               | `test_fix_converges.py` runs it (P11) |
| `grep -n "^                                                                                                                                                         | P\|^                                                                                   | M" docs/docs/dev/architecture.md`     | 8 rows | 17 rows |
| `clean.DIRS` against `_files.EXCLUDED_DIRS`                                                                                                                         | 8 shared names, 3 only in `DIRS` (`.coverage_html`, `.benchmarks`, `.hypothesis`)      | one source (3.4)                      |
| public names of the 13 task modules that are not tasks nor `NAMESPACE`                                                                                              | 22                                                                                     | 0 (M2)                                |
| `python -X importtime -c "import invoke_tasklib"`, `time inv --list`                                                                                                | 72 ms (cumulative), 0.08 s wall; 0.14 s                                                | not slower (M4)                       |
| `ruff check`, `ruff format --check`, `ty check`, `inv test.doctest`                                                                                                 | clean, clean, clean, 47 files pass                                                     | clean                                 |

What this says: the package behaves well on every case that earlier reviews fixed; this review found
no failing behaviour on `main`. The findings are about rules that are true by habit and not by a
written, tested statement (F1, F2, F3, F5), and about repetitions that earlier cleanups left
(F4, F6, F8, F9, F10). None of the target behaviours is a new capability; each one removes a
special case or states a rule.

## 7. Changes to reach the target state

One branch and one pull request per row, as in `CLAUDE.md`. "Breaking" means a public name or a
behaviour changes (section 4). Rows that touch the same files are stacked in the order given; the
others branch from `main`.

| Step | Change                                                                                                                                                                                                                                              | Breaking                        |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| 1    | **Write the contract (F1, F12).** The 17 properties into `architecture.md`, each marked tested or not; fix the `check.STEPS` docstring; add the `NAMESPACE` docstrings of `lint` and `imports`. Documentation only.                                 | no                              |
| 2    | **State and test the composition rule (F2, P12).** One sentence in `uguide/check.md` and `fix.md`; a test that `make_ns(exclude=...)` leaves `check.STEPS` untouched and that `check.all` follows `tasklib.check.tasks`. Stacked on 1 (same pages). | no                              |
| 3    | **Test that a fix leads to a passing check (F3, P11).** `tests/integration/test_fix_converges.py`. If it finds a mismatch between a `fix` and its `check`, fix the task in the same pull request and say so.                                        | no                              |
| 4    | **Remove the parameters nobody varies (F4).** `skip_missing` and optional `cfg` of `_run_pytest`, delete `_find_markdown_files`. Same tests, fewer lines.                                                                                           | no (private)                    |
| 5    | **`clean` reads the config once (F10).** `_try_config`, passed to the three helpers.                                                                                                                                                                | no                              |
| 6    | **One list of directories (F6).** `CACHE_DIRS`, `OUTPUT_DIRS`, `ENVIRONMENT_DIRS` in `_files`; `clean.DIRS` derived; a test that every directory of `clean.DIRS` is in `EXCLUDED_DIRS`. Stacked on 5 (same file).                                   | behaviour (three more skipped)  |
| 7    | **Isolate the Invoke internals (F7, M5).** `config/_invoke.py`; `show` and `_resolve` use it; the AST test of M5. Stacked on nothing (it touches `show.py`, `config/`).                                                                             | no (`show.LEVELS` moves)        |
| 8    | **Validators take the path (F9).** `_validate_*` receive `tasklib.<section>.<key>`; delete the repeated `partial` arguments; move `main` to `__main__.py`. Stacked on 7 (same package).                                                             | no (private)                    |
| 9    | **Every key is an `Unset` in `default_config` (F8).** Delete `_untyped`; a test that an environment variable of each type reaches `get_config` (integration, no patch). Stacked on 8.                                                               | yes (`default_config()` values) |
| 10   | **Tidy `release.py` (F11).** `split_args` in `_build_targets`, constants at the top, `_credentials`. Same behaviour, same tests plus the ones of `_credentials`.                                                                                    | no                              |
| 11   | **Make the task modules' extra names private (F5, M2).** The 22 names get a `_`; the test of M2 extends to the task modules; trim `docs/refs/`. Last of the breaking steps: it comes after 4, 5, 6, 7 and 10, which touch the same names.           | yes                             |
| 12   | **Release `0.1.0`.** The notes list the breaking rows (9, 11) and the one behaviour row (6) with the replacement for each name. Needs a decision to ship (it was step 13 of the previous plan).                                                     | -                               |

**Status.** Steps 1-3 are merged (#354-#356) and step 7 is in #361; no other step is started; the six decisions of section 9 are made, so no step waits on one. The previous plan's steps 1-12 are merged (#334-#349,
#350 for the tracking page); its step 13, the release, is the last row above.

Order: 1 first (it is the baseline of the contract), then 2. 3 is independent and can go at any
time; it is worth running early because it may find a real defect. 4, 5, 7 and 10 are independent
of each other. 6 follows 5, 8 follows 7, 9 follows 8. 11 comes last of the code steps. Update the
changelog or status table with the pull request number in each step.

## 8. Tests and gates

- **Contract (steps 1-2).** `test_architecture.py` gains: the readers of `os.environ` in `src/`
  equal the set of section 3.7 (P1); a test that every property row of `architecture.md` has the
  three columns filled (so a property is never added without its enforcement). `make_ns` test: with
  `exclude="lint"` the namespace has no `lint.check-python` and `check._STEPS["lint"]` is still
  there (P12).
- **Fix converges (step 3, P11).** One integration test on a git probe project, no patching:
  `inv fix.all`, then `inv check --only format-python,lint`, then a second `inv fix.all` and
  `git diff --stat` unchanged. Add a case with `format-docstrings` if `docformatter` is installed.
- **`testing` (step 4).** The existing tests of `unit`, `integration`, `functional` and `all_` still
  assert the whole list of commands (`_commands(c) == [...]`); the tests of `_run_pytest` lose the
  two parameters. No new behaviour, so no new test beyond the signature.
- **`clean` (steps 5-6).** One test that `_try_config` returns `None` on an invalid config and the
  config otherwise; one that `all_` loads the config once (count the `load_config` calls with a
  counting stand-in, plus the existing integration test that `clean` works on a broken
  `invoke.yaml`). One test that every directory of `clean.DIRS` is in `EXCLUDED_DIRS`; one
  parametrized test that the walk skips each of the eleven cache and output names.
- **Invoke internals (step 7, M5).** Unit tests of `project_root`, `levels` and
  `missing_internals` with a `types.SimpleNamespace` that lacks an attribute (the warning path);
  the AST test: no `getattr`/`hasattr` of a string that starts with `_` outside `config/_invoke.py`.
  The existing `show` tests stay and pass unchanged.
- **Config (steps 8-9).** The validator messages are asserted by the existing tests of
  `tests/unit/config/`; they must pass unchanged, which is the proof that step 8 is a refactor. The
  test that `default_config()` equals a literal dict (the whole output) is updated to the all-`Unset`
  dict. An integration test, with the real `inv` and an `INVOKE_TASKLIB_*` variable of each type
  (`int`, `bool`, `str`, list), asserts the resolved value in `config.show`. Check that it fails
  without step 9 only if the probe of section 6 stops holding; it is a guard, not a regression test.
- **`release` (step 10).** Unit tests of `_credentials`: PyPI token, TestPyPI token, `UV_PUBLISH_TOKEN`
  only for PyPI, trusted publishing, nothing set. `_build_targets` with an unbalanced quote exits
  `2` (it raised a `ValueError` before the first command only by luck of the call order).
- **Public names (step 11, M2).** A test over the 13 task modules: every public module-level name is
  a `Task` or `NAMESPACE`. Not a test of the exports of `__all__`, which `CLAUDE.md` rules out.
- **Doctests.** New private functions get a `pycon` example as `CLAUDE.md` asks; this review has
  none (examples are `text`, never `>>>`).
- **Patched behaviour.** Every unit test that patches `shutil.which`, `importlib.util.find_spec` or
  the environment keeps its integration counterpart; step 9 adds the one for the environment
  variables.
- **Gates.** `ruff check`, `ruff format --check`, `ty check`, `pytest tests --cov` at 100%,
  `inv test.doctest`, `inv check.all --keep-going` and the nightly benchmark with
  `--benchmark-compare-fail=mean:50%`. Read `tests/benchmarks/test_init_benchmark.py` before and
  after steps 7 and 9, which touch the import path of `config`.

## 9. Decisions for the maintainers

All six decisions are made: D1 is "yes", and D2-D6 follow the recommendation.

**D1. Make the 22 extra names of the task modules private (step 11).** _Recommended: yes, before
`0.1.0`._ A name in `docs/refs/` is a promise, and none of these is in the user guide. An alpha is
the cheap moment to say so. The alternative is to document the few that are useful (`clean.DIRS`
for a project that extends the cleanup) and keep them; that is more text to maintain for names that
nobody asked for.

Decision: yes. The 22 names become private in step 11, and they are listed in the `0.1.0` notes.

**D2. Composites ignore `make_ns(exclude=...)` (step 2).** _Recommended: keep, state it._ The steps
of `check.all` are chosen by `tasklib.check.tasks`, which is validated early (P5). Making the
composite read the namespace would couple `check` to `make_ns` and make the same `invoke.yaml`
behave differently under two `tasks.py` files. The alternative (the composite skips the excluded
tasks) is about 15 lines, but it silently shortens `check.all`, which is the wrong failure for a
quality gate.

Decision: follow recommendation

**D3. `default_config()` returns an `Unset` for every key (step 9).** _Recommended: yes._ It removes
the integer special case and the defaults that nobody reads. The cost is that `c.config.tasklib.*`
no longer shows the default values; the supported readers are `load_config` and `config.show`.
Step 9 ships in `0.1.0`.

Decision: follow recommendation. The `0.1.0` notes say that `default_config()` returns an `Unset`
for every key.

**D4. `release.build` keeps reading `--out-dir`, `--wheel` and `--sdist` from `--args` (step 10).**
_Recommended: keep, with `split_args`._ The alternative is that `release.build` owns the directory
(`dist`, or `tasklib.paths.dist`) and refuses `--out-dir` in `--args`. It deletes `_build_targets`
(20 lines) but adds either a refusal or a config key, and it breaks `uv build` habits. Not worth it.

Decision: follow recommendation

**D5. Keep `INVOKE_TASKLIB_ASCII` an environment variable, not a config key.** _Recommended: keep._
It is a property of the terminal, not of the project: the same project needs `1` on one machine and
nothing on another. A config key would live in the committed `invoke.yaml`. Section 3.7 lists it so
it is a documented exception to "the config is the only input".

Decision: follow recommendation. The variable stays; section 3.7 and the test of P1 list it.

**D6. Test P11 before deciding anything else about the fixes (step 3).** _Recommended: yes._ This
is the only step that can find a real defect. If `fix.all` and `check.all` disagree, the fix to the
task is the first priority and may change the order of the other steps.

Decision: follow recommendation. Step 3 runs early, right after step 1.

## 10. Not covered

- **Downstream registration of steps** (`make_ns(steps=...)`, a project adding its own step to
  `check.all`). With `check._STEPS` private (F5) this is further away, not closer; it needs a public
  step API and no project asks for it yet.
- **Windows support.** See section 1.
- **Other installers than `uv`.** `env.*`, `release.*` and `security.audit` call `uv`; the README
  says so.
- **Changing the tools** (ruff, ty, docformatter, codespell, mike). `types.checker` already covers
  the one that mattered.
- **`.make/`, `Makefile`, the workflows and `dev/`.** Not part of the package. The workflows need
  no change for this plan.
- **Machine-readable output** (`--json` for `check.all`). Useful, but a new feature.
- **Parallel steps.** The steps run in order on purpose (the fixes converge in order, P11).
- **Rewriting the user guide.** Only the pages listed in section 5 change.
- **The tests themselves.** 1,579 test functions were not reviewed one by one; only the ones named
  above were read.

## Appendix A. Effect on package size

"Lines" is the length of the file; "code" is the number of non-blank lines once the docstrings are
removed (measured with `ast`). "After" is an estimate, not a measurement.

| Module                | Lines today | Code today | Expected after (lines) | Why                                                            |
| --------------------- | ----------: | ---------: | ---------------------: | -------------------------------------------------------------- |
| `config/_schema.py`   |         519 |        117 |                    470 | no `_untyped`, no repeated keys, `main` moves out              |
| `config/_validate.py` |         567 |        120 |                    540 | `section` and `key` arguments replaced by the path             |
| `config/_invoke.py`   |           — |          — |                     90 | new (moved code, docstrings); tests move with it               |
| `config/_resolve.py`  |         188 |         51 |                    160 | the guard moves to `_invoke`                                   |
| `show.py`             |         223 |         62 |                    190 | `LEVELS` and the internals check move out                      |
| `testing.py`          |         469 |        126 |                    440 | two parameters and one wrapper fewer                           |
| `clean.py`            |         417 |        131 |                    400 | one config read, derived directory list                        |
| `_files.py`           |         199 |         41 |                    210 | three named sets                                               |
| `release.py`          |         414 |        133 |                    420 | gains `_credentials` and its docstring, loses the double parse |
| the rest (13 files)   |       4,382 |      1,241 |                  4,380 | unchanged (docstrings of the renamed constants only)           |
| **Total**             |   **7,377** |  **2,022** |             **~7,300** | about -1%; the unit tests shrink by about the same share       |

The saving is small on purpose: the package is already compact, and its length is mostly docstrings
and doctests that the project requires (code is 27% of the lines). The gain is not the size. It is
that the contract is written where a maintainer looks for it, that a fix and its check are proved to
agree, and that the public surface is the one the guide documents.

## Appendix B. How this was checked

- **Read:** every module of `src/invoke_tasklib/` (with `ast` to print the code without the
  docstrings), `pyproject.toml`, `invoke.yaml`, `tasks.py`, `CLAUDE.md`, `architecture.md`,
  `custom_tasks.md`, the README and user guide task tables, the previous `review/target_state.md`
  and `review/suggestions.md`, and `tests/unit/test_architecture.py`.
- **Ran:** `pytest tests --cov` (3073 passed, 13 skipped, 100%), `ruff check`, `ruff format --check`,
  `ty check`, `inv test.doctest`; `grep` and `ast` scripts for the findings F2-F8 and F12; the
  `Unset` probe with the real `invoke.Config`; the `make_ns(exclude=)` probe in a throwaway git
  project; `python -X importtime` and `time inv --list`.
- **Not run:** the target. No prototype exists except the `Unset` probe, so the "Target" column of
  section 6 and the "after" column of Appendix A are specifications and estimates. Findings marked
  **[reading]** (F4's wrapper, F7's imports, F9, F10, F11) need a second look in the pull request of
  their step. `release.publish`, `doc.publish-*`, the workflows and CI were not run or looked at.
