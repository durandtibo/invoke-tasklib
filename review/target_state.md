# `invoke_tasklib`: target state and the changes to reach it

This document proposes the target state of the `invoke_tasklib` package and the sequence of small
changes that gets there from `main` (`17389ab`, `0.1.0a0`). It replaces the previous target state,
whose 12 + 10 steps are all merged; the old text stays in the git history. It follows the principles
of the documentation (`docs/docs/dev/architecture.md`, `CLAUDE.md`, the user guide): one config
entry point, convention over configuration, composable tasks, no hidden state, a read-only
`check_<x>` for every mutating `fix_<x>`. Breaking changes are accepted (the package is an alpha),
and the future state weighs more than the past one.

The previous rounds removed the duplicated tables, split the support modules and wrote the contract.
What is left is of another kind. The package still builds a command as a **string and parses it
back** to find the program, still lists the steps of a composite in **four places**, still catches
the errors of a step with a **hand-written list** that misses some, and still starts a **subprocess**
only to call a function. Each of these is small; together they are most of the rules that a
maintainer has to remember. The target removes them instead of documenting them. It adds no task, no
dependency and no option.

**Evidence labels.** **[verified]** means reproduced by running code (the `.venv` tools, or a
throwaway project in the scratchpad, outside the repository). **[reading]** means found by reading
the source and not run. Line counts are `wc -l` of the files; the size of a change is an estimate
and is labelled as such.

**What was not changed.** No source file or test was changed to write this document. `release.publish`,
`doc.publish-*`, the workflows and CI were not run or looked at.

**Baseline on `main`** [verified]: `pytest tests -q` 3126 passed, 13 skipped (the `mike` tests: the
`docs` group is not installed here); `ruff check src tests` and `ty check` clean. `import
invoke_tasklib` takes 66 ms under `python -X importtime`, 32 ms of them for `invoke.collection`.
Source: 7,471 lines in 31 files (task modules 2,974, `config/` 1,604, support modules 1,820, the
import graph and the module discovery 825, `__init__.py` 248); tests: 14,816 lines.

## Constraints

1. **Simple and easy to maintain.** The only runtime dependency stays `invoke`. A change is accepted
   when it deletes more than it adds, or when it turns an unwritten rule into a test. No plug-in
   system, no new option, no new abstraction layer.
2. **Breaking changes are allowed, in one release.** They ship together in `0.1.0` and are listed in
   its notes. The task names, the task options, the `make_ns` signature and the **keys** of
   `invoke.yaml` do not change, so a project's `tasks.py` and `invoke.yaml` keep working. What breaks
   is the Python API of `runner` and `tools` (section 4) and one moment of validation (D1).
3. **Start-up cost is a floor.** `import invoke_tasklib` stays below 100 ms (M4). Nothing in the
   target imports more than today; the target imports `shlex` in fewer modules, not more.
4. **One convention per concern**, as in `CLAUDE.md`: read the config with `load_config`, run a
   command with `runner.run`, print with `output.say`. A rule that has no test is not a rule
   (section 8).
5. **Match the surrounding code**: docstrings, naming, test style and the three-line section headers
   of the tests stay as they are. No reformatting of code that a step does not change.

## 1. Properties of the sub-package

These are the properties that the package guarantees to a project that uses it (`P1`-`P12`), then
those it guarantees to its maintainers (`M1`-`M6`). They are the 17 properties of
`docs/docs/dev/architecture.md`, read again against the code: **P1, P4, P7, M2 are sharpened and M6
is new**; the others are unchanged. The last column says what enforces each one, or **new:** what
this plan adds (section 8).

| #   | Property                | Statement                                                                                                                                                                                                                                                                                                  | Enforced by                                                                                                      |
| --- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| P1  | One entry point         | The config is read with `load_config`; a command runs through `runner.run` or `runner.capture`; a message goes through `output.say`, `step` or `report_failure`. The only environment variables read are the ones listed in the user guide.                                                                | `test_architecture.py` (AST scan of `src/`)                                                                      |
| P2  | Read-only is read-only  | `check_<x>`, `check.all`, `test.*`, `types.check`, `imports.*`, `security.audit` and `config.show` never change a tracked file. Their only writes are caches and the coverage reports.                                                                                                                     | `tests/integration/test_read_only.py`                                                                            |
| P3  | Mutation is declared    | A task that changes files, the environment or a remote is named `fix_*`, or is a verb (`publish`, `build`, `install`, `clean`), and is marked in the README table.                                                                                                                                         | `test_init.py`; `tests/integration/test_readme.py`                                                               |
| P4  | Exit codes              | `0` pass, or nothing to do (a `⏭️` line says why); `1` the checked thing failed; `2` invalid usage or config; `127` a tool or module is missing. The failure line is `❌ Failed: <what>` on stderr. **With `--keep-going`, every step runs and every failure of an `Exception` is listed in the summary.** | `tests/integration/test_exit_codes.py`; **new:** `test__steps.py` (any `Exception`, not a closed list)           |
| P5  | Fail before acting      | An unknown key, an invalid value or a wrong working directory exits with `2` before any command runs. The message names the key.                                                                                                                                                                           | `config/_validate.py`, `_check_project_root`; `tests/unit/config/`                                               |
| P6  | Missing tools           | A missing program or Python module is reported with the command that installs it. A composite task reports all the missing tools of its steps at once, and runs nothing.                                                                                                                                   | `tools.hint`, `_steps.preflight_message`; `tests/unit/test_check.py`                                             |
| P7  | Commands are data       | A task builds a command as **a list of words**; `runner.run` is the only place that turns it into a shell line (`shlex.join`) and it rejects a string. A space, `;`, `*`, `~` or `$VAR` in a user value reaches the tool unchanged.                                                                        | **new:** AST test (no `shlex.quote` or `shlex.split` in a task module); `tests/integration/test_quoting.py`      |
| P8  | One source of truth     | A config key is declared once (`SCHEMA`), a tool once (`TOOLS`), a step once (`STEPS`, with its order and whether it is a default), a directory policy once (`_files`). Defaults, the JSON schema, the hints and the docs tables derive from them.                                                         | tests that compare the tables; **new:** the step names exist only in `STEPS` (D1)                                |
| P9  | Safe by default         | A destructive task stays inside the project, keeps what git tracks, and asks before an irreversible step. A credential never appears in a command line or in the output.                                                                                                                                   | `clean._is_inside_project`, `release._check_release_state`, `_publish_environment`; `tests/unit/test_release.py` |
| P10 | Skips are visible       | A task that has nothing to do prints `⏭️ <reason>` and exits `0`. A task that cannot do its job (a path it needs is missing) exits non-zero and names the key.                                                                                                                                             | `_files.require_path`; `tests/unit/test__files.py`, `tests/integration/test_files.py`                            |
| P11 | Fix converges           | After `fix_<x>` (or `fix.all`) the matching `check_<x>` passes, and a second `fix_<x>` changes nothing.                                                                                                                                                                                                    | `tests/integration/test_fix_converges.py`                                                                        |
| P12 | Composition is explicit | `make_ns(include=, exclude=)` selects the tasks that the command line offers. The steps of `check.all` and `fix.all` come only from `tasklib.check.tasks` and `tasklib.fix.tasks`; excluding a task from the namespace does not remove its step.                                                           | `test_init.py`, `uguide/check.md`, `uguide/fix.md`                                                               |
| M1  | Layers                  | A task module imports only the support modules, never another task module. The two composites (`check`, `fix`) import task modules and `_steps`. `config`, `tools` and `output` import nothing of the package that is above them.                                                                          | `test_architecture.py` (layering test on `_graph.import_graph`)                                                  |
| M2  | Public means documented | A name is public only if it is in the `__all__` of its module and in the user guide. **A task module has no public name except its tasks and `NAMESPACE`**; every other name starts with `_`.                                                                                                              | `test_architecture.py`; **new:** the same test for the 13 task modules (F5)                                      |
| M3  | Every function tested   | Every function, private ones included, has a docstring, a unit test and, if the unit test patches a collaborator, an integration test. Coverage is 100% (lines and branches). A function has no parameter that every caller passes the same.                                                               | `test_docstrings.py`, `--cov-fail-under=100`, `CLAUDE.md`                                                        |
| M4  | Cheap to import         | `import invoke_tasklib` stays below 100 ms; `make_ns()` does no I/O.                                                                                                                                                                                                                                       | `tests/benchmarks/test_init_benchmark.py`                                                                        |
| M5  | Invoke internals apart  | The private attributes of `invoke.config.Config` are read in one module, `config/_invoke.py`, which warns when one is missing.                                                                                                                                                                             | `test_architecture.py`                                                                                           |
| M6  | Declared equals run     | The programs and modules that a `Step` declares are exactly those that its task runs with a check. A tool that a task runs and the step does not declare would be missing from the preflight (P6); one that is declared and not run blocks a step for nothing.                                             | **new:** `test_check.py` / `test_fix.py` record the commands of every step (F3)                                  |

**Not guaranteed, and documented as such:**

- **Windows.** The tasks need a POSIX shell for `c.run`. `make_ns` warns; nothing else is done.
- **A skipped step is not a checked step.** `check.all` prints `⏭️` for the `unit` step of a project
  without `tests/unit`, then `✅ All checks passed` (P10, decision D5 of the first target state).
- **Private Invoke attributes.** `config.show` and the working-directory guard read private
  attributes of `invoke.config.Config`; M5 keeps them in one module and warns, which is all that can
  be done without a public API.
- **Tool versions.** `ty` is `0.x`; the checker is configurable (`tasklib.types.checker`).
- **Stale installs.** `imports.check-isolated` tests the package that the interpreter finds, not a
  built artifact; `release.build` tests the artifact. Both say so in their docstrings.
- **Every cycle.** `imports.check-cycles` reports one cycle per strongly connected component.

## 2. What differs today

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Status                             |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| F1  | **A command is built as a string, then parsed back.** A task writes `build_command("ruff format --check", ...)` (the program and its sub-command words are one unquoted string, the rest is quoted), `runner.run` calls `check_program(command)`, which does `shlex.split`, strips `NAME=value` words (`_strip_assignments`) and skips nine shell builtins (`_UNCHECKED_PROGRAMS`) to find the program again. Tasks also call `shlex.quote` 19 times by hand for what `build_command` does not cover. No task uses a shell operator (`&&`, `\|`, `>`, `$(`), no task sets a variable in front of a command, and only one uses a builtin (`command -v python` in `env.show-python-config`); the other 8 builtins of the list are unused. The quoting rule (P7) holds by discipline and is proved by an integration test, not by the structure. | [verified] (`grep`)                |
| F2  | **`STEP_ERRORS` is a closed list of nine exception types.** `run_step` is meant to turn any failure of a step into a line of the `--keep-going` summary, but `EOFError`, `StopIteration` and `subprocess.TimeoutExpired` escape it: the whole run ends with a traceback and no summary. `KeyboardInterrupt` and `SystemExit` are not `Exception`, so `except Exception` already leaves them alone; the list adds nothing but the gaps.                                                                                                                                                                                                                                                                                                                                                                                                        | [verified] (probe, section 6, E2)  |
| F3  | **What a step declares and what its task runs are two facts with no test between them.** `Step.programs` and `Step.modules` repeat the first word of the commands of the task. They are right today (probe E3: all 15 steps), but a new `run(c, ...)` in a task that the step does not declare is invisible until a user lacks the tool in the middle of `check.all` and P6 (all missing tools at once, nothing run) is broken.                                                                                                                                                                                                                                                                                                                                                                                                               | [verified] (probe, section 6, E3)  |
| F4  | **A step is listed in four places.** The name is in `CHECK_STEPS`/`FIX_STEPS` of `config/_constants.py` (the config cannot import the task modules) and in `check.STEPS`/`fix.STEPS`; the defaults are `CHECK_STEPS[:6]` and `FIX_STEPS[:3]`, a slice whose meaning is its position; the tools are in `Step` and in `TOOLS`. `check.py` and `fix.py` import `config._constants`, a private module of another package, and a test keeps the two lists equal. The page `architecture.md` needs a four-point recipe to add a step.                                                                                                                                                                                                                                                                                                               | [verified] (`grep`) + [reading]    |
| F5  | **The task modules expose 21 public names that are not tasks.** `clean`: `DIRS`, `DIR_GLOBS`, `FILES`, `FILE_GLOBS`, `SITE_DIR`, `MKDOCS_CONFIGS`; `env`: `PRE_COMMIT_CONFIG`, `VENV_DIR`, `LOCK_FILE`; `release`: `TWINE_REQUIREMENT`, `TEST_PYPI_PUBLISH_URL`, `TEST_PYPI_CHECK_URL`, `PUBLISH_CREDENTIAL_VARIABLES`; `testing`: `COV_HELP`, `APPEND_HELP`, `PYTEST_HELP`, `APPEND_PYTEST_HELP`; `typecheck`: `COMMANDS`; `security`: `PIP_AUDIT_REQUIREMENT`; `check.STEPS`, `fix.STEPS`. Two are named in the user guide (as a version range), none is in an `__all__`. M2 says nobody promised them; `docs/refs/` renders them as API.                                                                                                                                                                                                   | [verified] (`grep`)                |
| F6  | **Stale statements about the defaults.** `Option.default` says "a default is a string for a list, so that `INVOKE_TASKLIB_<SECTION>_<KEY>` can override it", which stopped being true when every key became an `Unset`. The lists are still strings (`"dev,docs"`, `"html,xml,term"`, `"format-python,..."`) that the validators split again, and `json_schema()` publishes them as the `default` of a key whose type is an array. The docstring of `get_config` lists six sections; there are seven (`types`).                                                                                                                                                                                                                                                                                                                               | [verified] (probe E6) + [reading]  |
| F7  | **`imports.check-isolated` starts a subprocess to call a function.** The task runs `python -m invoke_tasklib._discover --import-each <pkg>` with `sys.executable`, reads a tab-separated text protocol (`_parse_import_each`) and shows nothing of the process: the worker is the same interpreter, with the same working directory, which `_check_project_root` already forces to be the directory of `tasks.py`. The worker then starts one interpreter per module itself. The other mode of `_discover.main` (print the module names) has no caller in the package.                                                                                                                                                                                                                                                                        | [verified] (`grep`, probe E5)      |
| F8  | **The same two-entry `help` dict is written 13 times**, and `ARGS_HELP` alone 8 more (`formatting` 7, `testing` 4, `lint` 2 for the pair). `testing` has its own `PYTEST_HELP` for one module.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | [verified] (`grep`)                |
| F9  | **A stray file is tracked.** `review/target_state.md-e` is the backup that `sed -i` leaves on macOS. It is not markdown, so no test reads it, but it is in the repository.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | [verified] (`git ls-files review`) |

**Already correct, and must not regress.** The strict config (unknown key with a suggestion, `null`
rejected for an integer, the working-directory guard), the exit-code convention, the preflight of
the tools of a composite and `--keep-going`, the ASCII fallback of `output.say`, `release.build`
verifying the artifact with `python -I`, the scrubbed credentials of `uv publish`, `clean` refusing
paths outside the project and tracked directories, the single `step` helper, the missing-path rule
and `require_path`, `imports.check-cycles` reading `paths.src`, `run_composite` shared by `check.all`
and `fix.all`, one `TOOLS` registry, one `_Version` in `doc.py`, one reader of the private Invoke
attributes (`config/_invoke.py`), one list of excluded directories (`_files`), the integration test
that a fix leads to a passing check, and 100% coverage.

## 3. Architecture

The layers do not change except for the removal of the worker. They are enforced by
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
   L2   _steps   _files   _coverage   _pyproject   _graph   _discover
               │
   L1   config/   runner   tools   output                    support: the documented helpers
               │
   L0   (stdlib, invoke)
```

`_discover` moves from L0 (a worker with no import of the package) to L2: once it is a function
called by a task it is an ordinary helper (3.5).

### 3.1 A command is a list of words (F1, F8)

```python
# runner.py
def build_command(
    words: Sequence[str],
    *,
    args: str | None = None,
    paths: str | None = None,
    default_paths: Sequence[str] = (),
    args_option: str = "--args",
) -> list[str]:
    """The words, then the split ``args``, then the paths (or the default paths)."""
    return [
        *words,
        *split_args(args, args_option),
        *(split_args(paths, "--paths") or default_paths),
    ]


def run(c: Context, command: Sequence[str], *, check: bool = True, **kwargs: Any) -> Result:
    if isinstance(command, str):
        raise TypeError("pass the command as a list of words, e.g. ['ruff', 'check', '.']")
    if check:
        check_program(command)
    ...
    return c.run(shlex.join(command), **kwargs)  # the only place that quotes
```

A task becomes:

```python
run(c, build_command(["ruff", "format", "--check"], args=args, paths=paths, default_paths=["."]))
run(c, ["uv", "venv", *(["--python", version] if version else []), "--clear"])
run(c, [python_executable(), "-m", "pytest", "--xdoctest", *paths])  # no shlex.quote anywhere
```

- `check_program(command: Sequence[str])` reads `command[0]`; if the word is `sys.executable` and
  the next one is `-m`, it checks the module (and the pytest plugins of the options), otherwise it
  looks the program up. `_strip_assignments`, `_ASSIGNMENT`, `_UNCHECKED_PROGRAMS` and the
  `except ValueError: return` of the `shlex.split` go away. `python_executable()` returns the path
  unquoted.
- `capture` and the `env=` / `replace_env=` of `uv publish` are unchanged.
- The unit tests still assert on the **string** that `c.run` receives (`_commands(c) == [...]`), so
  almost every command assertion stays as it is. What changes is the tests of `build_command`,
  `check_program` and the few helpers that call them directly.
- `env.show-python-config` ran `command -v python` through the shell; it prints
  `shutil.which("python")` with `say` instead (D3). It is the only task that needed a builtin.
- `runner.TOOL_HELP = {"args": ARGS_HELP, "paths": PATHS_HELP}` replaces the 13 repeated dicts;
  `testing.PYTEST_HELP` becomes `{**TOOL_HELP, "cov": ...}`.

### 3.2 Steps: one declaration, one test (F2, F3, F4)

```python
# _steps.py
class Step(NamedTuple):
    task: Callable[[Context], None]
    programs: tuple[str, ...] | Callable[[TasklibConfig], tuple[str, ...]] = ()
    modules: tuple[str, ...] | Callable[[TasklibConfig], tuple[str, ...]] = ()
    default: bool = True  # run when tasklib.<composite>.tasks is not set


def run_step(c, tasks, step) -> str | None:
    try:
        tasks[step](c)
    except UnexpectedExit as exc:
        ...
    except Exit as exc:
        ...
    except Exception as exc:  # any bug, OSError, timeout: the summary must still be written
        return f"{type(exc).__name__}: {exc}".removesuffix(": ")
    return None
```

```python
# check.py
_STEPS: dict[str, Step] = {            # the order is the order of the run
    "format-python": Step(formatting.check_python, programs=("ruff",)),
    ...
    "unit": Step(_unit, modules=_unit_modules),
    "doctest": Step(testing.doctest, modules=("pytest", "xdoctest"), default=False),
    "shell": Step(_shell, programs=("shellcheck", "shfmt"), default=False),
    ...
}
```

- `STEP_ERRORS` is deleted; `run_step` catches `Exception` after `UnexpectedExit` and `Exit`.
  `KeyboardInterrupt` and `SystemExit` still stop the run.
- The step names exist only in `_STEPS`. `config/_constants.py` loses `CHECK_STEPS`, `FIX_STEPS`,
  `DEFAULT_CHECK_STEPS` and `DEFAULT_FIX_STEPS`. `check.tasks` and `fix.tasks` default to `None`,
  which means "the steps with `default=True`, in order"; a value is validated for its shape in the
  config (non-empty list of strings) and for its **names** by `parse_steps`/`run_composite`, before
  any step runs, with the same message and the exit code `2` (D1). `check.py` and `fix.py` stop
  importing `config._constants`.
- Adding a step is two edits: the entry in `_STEPS`, and the tools in `TOOLS`. The uguide tables and
  the README are checked by the existing tests.
- M6 as a test, one per composite:

```text
for each step of _STEPS:
  patch runner.check_program to record the command it receives (and which commands pass check=False)
  run step.task against a MockContext with a minimal project
  programs = {command[0]} - {sys.executable};  modules = {command[2] for "-m" commands}
  assert (programs, modules) == step.needs(cfg)
```

The probe in section 6 (E3) is this test without the assertion; it passes today for the 15 steps,
so the step only adds the test.

### 3.3 Config: real defaults (F6)

- `Option.default` is the value: `("dev",)`, `("dev", "docs")`, `("html", "xml", "term")`, `10`,
  `True`. `_as_names` already accepts a tuple, so the validators do not change. `json_schema()`
  publishes arrays as the `default` of an array key. The sentence about environment variables is
  removed from `Option`; `default_config()` keeps the `Unset` and its explanation, which is where
  the rule lives.
- `check.tasks` and `fix.tasks` have the default `None` (3.2) and the dataclass field is
  `tuple[str, ...] | None`. The composite does `cfg.check.tasks or default_steps(_STEPS)`.
  `config.show` prints `tasks: null  # default` for them; the user guide says which steps that
  means.
- The docstring of `get_config` lists the seven sections. The `package.name` presence check stays
  (it gives the better message) and its second validation by `_validate_str` is dropped when the
  first check already proved the type.

### 3.4 The public surface of the task modules (F5)

- The 21 names of F5 become private (`_DIRS`, `_VENV_DIR`, `_TWINE_REQUIREMENT`, `_PYTEST_HELP`,
  `_COMMANDS`, `_STEPS`, ...). `NAMESPACE` stays. The two version ranges that the user guide quotes
  (`twine>=6.1,<7`, `pip-audit>=2.10,<3`) stay in the guide as text; a test already compares them with the code and
  is updated to read the private name.
- The architecture test of M2 loops over the 13 task modules: the public names (no leading
  underscore, defined in the module, not imported) are the `Task` objects and `NAMESPACE`.
- `docs/refs/` stops rendering the constants. Nothing else in the repository imports them except
  tests, which are updated with the rename.

### 3.5 `imports.check-isolated` calls the function (F7)

```python
# imports.py
total, failures = import_each(cfg.package.import_name)  # _discover.import_each, in process
for module, reason in failures:
    say(c, f"❌ {module}: {reason}", err=True)
```

- `_parse_import_each`, `_discover.main`, the `if __name__ == "__main__"` block and the tab protocol
  are deleted. `_discover` keeps `find_spec`, `discover_modules`, `_walk` and the asyncio
  `import_each`; `_graph` already imports the first three.
- Why this is safe: the task already requires that `inv` runs in the directory of `tasks.py`
  (`_check_project_root`), and Invoke puts that directory on `sys.path` when it loads `tasks.py`.
  In a flat-layout probe project the in-process `find_spec` finds the package (E5). The child
  interpreters of `import_each` are still one per module, so each module is still imported in a
  clean interpreter. A `ModuleNotFoundError` becomes `Exit(1)` with the same message as
  `check-cycles`.
- The import of the package is never done in the Invoke process: `find_spec` imports nothing, and
  the modules are imported by the children.

### 3.6 Housekeeping (F9)

`git rm review/target_state.md-e`. A test that no tracked file ends in `-e` or `~` is not worth
adding; a line in `CONTRIBUTING.md` about `sed -i ''` is enough.

## 4. Public API after the change

| Name                                                        | Before                            | After                                                                                                          |
| ----------------------------------------------------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `runner.build_command(program, ...)`                        | `-> str`, `program` is one string | `build_command(words, ...) -> list[str]` (**breaking**)                                                        |
| `runner.run(c, command)`                                    | `command: str`                    | `command: Sequence[str]`; a `str` raises `TypeError` (**breaking**)                                            |
| `runner.capture(c, command)`                                | `command: str`                    | `command: Sequence[str]` (**breaking**)                                                                        |
| `runner.python_executable()`                                | the quoted path                   | the path, unquoted (**breaking**; only used to build a command)                                                |
| `runner.TOOL_HELP`                                          | none                              | `{"args": ARGS_HELP, "paths": PATHS_HELP}`                                                                     |
| `tools.check_program(command)`                              | `command: str`                    | `command: Sequence[str]` (**breaking**)                                                                        |
| `tools.hint`, `find_tool`, `not_found_message`, `TOOLS`     | unchanged                         | unchanged                                                                                                      |
| `output.*`                                                  | unchanged                         | unchanged                                                                                                      |
| `config.get_config`, `load_config`, `SCHEMA`, `json_schema` | unchanged                         | unchanged; `cfg.check.tasks` and `cfg.fix.tasks` can be `None` (**breaking**), JSON schema defaults are arrays |
| `config` keys of `invoke.yaml`                              | unchanged                         | unchanged; a step name is validated by the composite (D1)                                                      |
| `check.STEPS`, `fix.STEPS`, 19 other task-module constants  | public by accident                | private (**breaking**, not documented before)                                                                  |
| `make_ns(include=, exclude=)`, task names, task options     | unchanged                         | unchanged                                                                                                      |
| `python -m invoke_tasklib._discover`                        | private worker                    | removed                                                                                                        |

## 5. Dependents

- **Projects that use the package** (`tasks.py` with `make_ns()`, `invoke.yaml` with `tasklib:`):
  no change. A project that lists `check.tasks` with a typo gets the same message and the exit code
  `2` from `inv check`, but no longer from an unrelated task such as `inv test.unit` (D1).
- **Projects with custom tasks that call `runner.run`, `runner.build_command` or
  `tools.check_program`** (documented in `uguide/custom_tasks.md`): they pass a list instead of a
  string. The error is a `TypeError` whose message gives the replacement.
- **This repository**: `tasks.py` uses only `make_ns` and `release.build`. The 32 workflows run
  `inv` task names, which do not change; the composite action `build-pypi-package-action` runs
  `inv build-package`, which `tasks.py` keeps. CI was not read in full [reading].
- **Documentation to update with the steps**: `docs/docs/dev/architecture.md` (properties P1, P4,
  P7, P8, M2, M6; "Adding a step"; layers; the `runner` and `tools` paragraphs),
  `uguide/custom_tasks.md` (the list API), `uguide/check.md` and `uguide/fix.md` (the default
  steps), `uguide/imports.md` (no worker command), `uguide/config.md` (`check.tasks` default),
  `uguide/env.md` (`show-python-config`), `docs/docs/schema.json` (array defaults, regenerated),
  `README.md` and `uguide/index.md` (nothing changes in the task table).

## 6. Evidence

All probes ran against `main` (`17389ab`) with the repository `.venv`, or in a throwaway project in
the scratchpad. No file of the repository was changed.

| #   | Probe                                                                                                                                                                      | Result                                                                                                                                                                                                                                                                                              |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E1  | `pytest tests -q`, `ruff check src tests`, `ty check`                                                                                                                      | 3126 passed, 13 skipped; both linters clean.                                                                                                                                                                                                                                                        |
| E2  | `run_step(None, {"s": boom}, "s")` where `boom` raises each of `KeyError`, `UnicodeError`, `NotImplementedError`, `EOFError`, `StopIteration`, `subprocess.TimeoutExpired` | The first three come back as a reason string. **`EOFError`, `StopIteration` and `TimeoutExpired` escape `run_step`**: with `--keep-going` the summary is not written.                                                                                                                               |
| E3  | Run the task of each of the 15 steps of `check.STEPS` and `fix.STEPS` against a context that records `c.run`, with `which` and `find_spec` patched                         | The first word of the recorded commands equals `Step.programs` for every step (`ruff`, `docformatter`, `ty`, `codespell`, `mkdocs`, `uv`/`uvx`, `shfmt`, ...). The shell steps also run `git ls-files`, with `check=False`: it is not required, and the M6 test must ignore a command run that way. |
| E4  | `grep` of the commands of `src/` for `&&`, `\|\|`, `\|`, `>`, `$(`, a leading `NAME=value`, and for the builtins of `_UNCHECKED_PROGRAMS`                                  | No match for the operators and the assignments. One builtin: `command -v python` (`env.py`). `shlex.quote` appears 19 times in the task modules (`doc` 5, `release` 6, `testing` 3, `security` 2, `env` 1, `lint` 1, `imports` 1) and 2 times in `runner`.                                          |
| E5  | A flat-layout project (`flatpkg/__init__.py`, `tasks.py` with a task that calls `_discover.find_spec("flatpkg")`), run with `inv`                                          | `find_spec` finds the package in the Invoke process; the tasks directory is on `sys.path`. `inv imports.check-isolated` passes today in the same project.                                                                                                                                           |
| E6  | `json_schema()` for `groups.install`, `test.cov_reports`, `check.tasks`                                                                                                    | `default` is `"dev"`, `"html,xml,term"` and `"format-python,format-docstrings,lint,types,imports,unit"`: strings, for keys that accept arrays.                                                                                                                                                      |
| E7  | `python -X importtime -c "import invoke_tasklib"`                                                                                                                          | 66 ms in total, 32 ms in `invoke`. The target removes imports of `shlex` from some modules and adds none.                                                                                                                                                                                           |

**Estimated size of the change** [reading, not measured]: about 150 lines of source deleted
(`tools.py` assignment and builtin handling, `STEP_ERRORS`, the worker protocol of `_discover` and
`imports`, the four step constants, the 19 `shlex.quote` calls, the 13 `help` dicts) and about 60
added (the `Step.default` logic, the type test in `run`, the M6 and M2 tests are in `tests/`). The
tests lose the cases of the deleted code and gain the ones of section 8; the net change in
`tests/` is expected to be small.

## 7. Changes to reach the target state

One branch and one pull request per row, in this order. Each row can be released alone. A row
marked **breaking** goes in the notes of `0.1.0`. Rows 1-5 are independent of each other; row 6
needs row 3; rows 7-10 are stacked and need row 2 (the test protects the refactor).

| Step | Change                                                                                                                                                                                                        | Breaking                         | Fixes  | PR  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- | ------ | --- |
| 1    | `run_step` catches `Exception`; delete `STEP_ERRORS`. Regression tests for `EOFError`, `StopIteration`, `TimeoutExpired` (they fail without the change); P4 sentence in `architecture.md`.                    | no                               | F2     | #371 |
| 2    | M6 test for `check.STEPS` and `fix.STEPS`: the commands of each step against `Step.needs`. Fix any drift it finds (none expected); `architecture.md` gets M6.                                                 | no                               | F3     | #372 |
| 3    | Real defaults in `SCHEMA` (tuples), `json_schema()` arrays, remove the stale `Option` sentence, fix the `get_config` docstring, regenerate `schema.json`.                                                     | no (schema defaults change type) | F6     | #373 |
| 4    | Private constants in the 8 task modules, `runner.TOOL_HELP`, M2 test over the task modules, update the tests and `docs/refs/`.                                                                                | yes                              | F5, F8 | #375 |
| 5    | `imports.check-isolated` calls `import_each`; delete `_discover.main`, `_parse_import_each`; `_discover` moves to L2 in the layer test and the docs.                                                          | no                               | F7     | #376 |
| 6    | `Step.default`; `_STEPS` is the only list of step names; `check.tasks` and `fix.tasks` default to `None` and are resolved by the composite; delete the four constants of `_constants` and the agreement test. | yes (D1)                         | F4     | #377 |
| 7    | `runner` accepts a list or a string (the string path is kept for now); `check_program` accepts both. New tests for the list path.                                                                             | no                               | F1     | #378 |
| 8    | Convert `formatting`, `lint`, `typecheck`, `security`, `testing`, `_files`, `clean`, `imports` to lists (no `shlex.quote`).                                                                                   | no                               | F1     | #379 |
| 9    | Convert `env`, `release`, `doc`; replace `command -v python` by `shutil.which` (D3).                                                                                                                          | no (output of one line)          | F1     | #380 |
| 10   | Remove the string path: `run` raises `TypeError`, delete `_strip_assignments`, `_ASSIGNMENT`, `_UNCHECKED_PROGRAMS`; P7 AST test; update `custom_tasks.md`, `architecture.md`.                                | yes                              | F1     | #381 |
| 11   | `git rm review/target_state.md-e`; the status column of this table gets the pull request numbers; `architecture.md` properties match section 1.                                                               | no                               | F9     | #382 |

## 8. Tests and gates

- **Every step**: `ruff check src tests`, `ruff format --check src tests`, `ty check`, `pytest tests
-q`, `inv test.doctest`; coverage stays at 100% (lines and branches). A regression test for every
  bug fixed, checked to fail without the fix (`git stash push src`).
- **Step 1**: one test per escaping type, each with `match=` on the message; the summary is asserted
  as a whole (`assert _commands(c) == [...]` and the output lines).
- **Step 2**: one parametrized test per composite over the step names; the test fails if a
  `run(c, ...)` is added to a task without a matching entry in the step. The commands run with
  `check=False` are ignored.
- **Step 4**: the M2 test lists the public names of each task module; a new constant without an
  underscore fails it.
- **Step 5**: an integration test for `imports.check-isolated` in a flat and in a `src` layout
  (E5), and one for a package with a module that fails to import.
- **Step 6**: unit tests for the default steps (`default=True`, in order), for an unknown name
  (`Exit` code `2`, message with the valid names, no command run) and for `config.show`.
- **Steps 7-10**: the unit tests of the commands do not change (they compare the string);
  `test_quoting.py` stays and must pass at every step. The P7 AST test goes in with step 10: no
  `shlex.quote` or `shlex.split` in a task module, and `run` raises `TypeError` for a `str`.
- **Gate**: `tests/benchmarks/test_init_benchmark.py` (M4) and the 100 ms bound do not move.

## 9. Decisions

The maintainer has answered all six; the plan of section 7 follows them.

**D1. Where are the step names checked?** _Recommended: in the composite, before any step runs._
The names are then declared once (`_STEPS`) and adding a step is two edits. The costs: `inv
test.unit` with a typo in `check.tasks` no longer fails (it was an unrelated failure), `config.show`
does not flag it, and the JSON schema loses the `enum` of the step names (an editor no longer
completes them). The alternative is to keep `CHECK_STEPS`/`FIX_STEPS` in `config/_constants.py`,
make `DEFAULT_*` explicit tuples instead of slices, and export the names from `config`; that keeps
the editor completion and the early failure at the price of the four-place recipe.

**Decided: the step names are checked by the composite, before any step runs.** The plan keeps `_STEPS` as the only list (steps 6 and 10 of section 7); the `enum` of the JSON schema is dropped.

**D2. Does `run` keep accepting a string?** _Recommended: no, a `str` raises `TypeError`._ Keeping
both would keep `_strip_assignments`, the builtins list and the quoting rule by discipline, which is
the point of F1. The alpha version is the time to break it.

**Decided: `run` rejects a string** with a `TypeError` (step 10).

**D3. What replaces `command -v python`?** _Recommended: `say(c, shutil.which("python") or "python: not found")`._
The alternative is to delete the line: `uv python find` right above it prints the interpreter that
uv would use, which is the useful answer; the `PATH` one is only informative.

**Decided: `env.show-python-config` prints `shutil.which("python")`** with `say` instead of `command -v python` (step 9).

**D4. Is the worker of `check-isolated` worth keeping?** _Recommended: no (3.5)._ The one reason to
keep a process boundary would be a `sys.path` that differs from the project's; E5 shows that it does
not for a project that passes `_check_project_root`.

**Decided: no worker.** `imports.check-isolated` calls `import_each` in process (step 5).

**D5. Underscore the constants, or add an `__all__` and document them?** _Recommended: underscore._
Nobody asked for a public `clean.DIRS`; a name becomes public when the user guide needs it.

**Decided: the 21 constants become private** (step 4); none gets an `__all__`.

**D6. Windows.** Unchanged: a warning, no support.

**Decided: a warning, no support.** Nothing changes.

## 10. Not covered

- **Not changed, deliberately.** The dataclass of each config section next to its `SCHEMA` options
  (a test keeps them equal and `ty` needs the classes); the leading underscore of the functions that
  are shared between the modules of `config/` (renaming about 25 functions and their tests for no
  behaviour); `show.py` importing `config._invoke` (M5 allows its one reader, and `show` is its
  user); `_graph.py` (499 lines for `check-cycles`: Tarjan, a shortest cycle and the import rules;
  100% covered, and the `--lazy` and `--type-checking` options are documented); the ASCII fallback
  of `output.say`; `clean` having its own walk (the `__pycache__` directories are ignored by git);
  the version and `mike` parsing inside `doc.py` and the credential lookup inside `release.py`
  (private to one task each); `load_config` called by each task (it is cheap: no I/O but one
  `is_dir`); the module name `show` for the namespace `config`.
- **Not reviewed.** The workflows, the 3,126 tests beyond their rules in `CLAUDE.md`, `docs/docs/uguide/`
  beyond the passages named above, `dev/`, and `.make/`.
- **Not run.** `release.publish`, `doc.publish-dev`, `doc.publish-latest`, `env.create-venv`,
  `env.update`, and the 13 skipped `mike` tests.

## Appendix: size of the package today

| Group                                                                                | Files | Lines  | Notes                                                                                    |
| ------------------------------------------------------------------------------------ | ----- | ------ | ---------------------------------------------------------------------------------------- |
| Task modules (`formatting` ... `show`)                                               | 13    | 2,974  | `release` 449, `clean` 425, `testing` 424, `doc` 399, `env` 246, `show` 173, `check` 168 |
| `config/`                                                                            | 8     | 1,604  | `_validate` 577, `_schema` 450, `_resolve` 180, `_invoke` 160                            |
| Support (`runner`, `tools`, `output`, `_steps`, `_files`, `_pyproject`, `_coverage`) | 7     | 1,820  | `tools` 450, `_steps` 372, `runner` 308, `output` 251                                    |
| `_graph`, `_discover`                                                                | 2     | 825    | `_graph` 499, `_discover` 326                                                            |
| `__init__.py`                                                                        | 1     | 248    | `make_ns`, `_MODULES`                                                                    |
| **Source**                                                                           | 31    | 7,471  | docstrings are about half of the lines                                                   |
| **Tests**                                                                            |       | 14,816 | 3,126 tests                                                                              |
