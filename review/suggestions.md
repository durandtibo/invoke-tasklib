# Review of `invoke-tasklib` — suggestions

This review replaces the previous one (#228). The code was read again from the start, and the old
text stays in the git history. Almost everything in the old review has been done since (see
"What happened to the previous review"), so this one is about what is left and what the fixes
uncovered.

## Scope and method

Read line by line:

- `src/invoke_tasklib/`: all 27 files (6,196 lines), including `config/`, `_steps.py`, `_graph.py`,
  `_discover.py` and `_files.py`;
- `pyproject.toml`, `invoke.yaml`, `tasks.py`, `CLAUDE.md`, `docs/docs/dev/architecture.md`, the
  head of `.pre-commit-config.yaml`.

Checked with tools or scripts, not read in full:

- the test tree (`tests/`, 8,895 lines in `unit/` and `integration/`): an `ast` script for the rules
  of `CLAUDE.md` (asserts per test, logic, `match=`, local imports), plus `grep`;
- the 31 CI workflows: `grep` for top-level `permissions:`, for actions not pinned to a SHA, and for
  the `inv` tasks they run. They were **not** read in full.

Not reviewed: `.make/` (vendored), `docs/docs/uguide/*` and `docs/docs/refs/*` beyond the greps
above, `dev/`, and the content of most of the 2,506 tests.

Baseline on `main` (`f56b4d2`): `pytest tests` 2506 passed, 12 skipped in 13 s; coverage 100%
(lines and branches); `ruff check` and `ty check` clean. The doctests and CI were not re-run.

Legend: **[verified]** reproduced with the real tools or a probe project (kept outside the
repository); **[reading]** found by reading, not run. Severity: high / medium / low.
**[breaking]** changes a public behaviour or signature (allowed by the request).

## Summary: what to do first

1. Boolean and integer values given as `INVOKE_TASKLIB_*` environment variables are wrong:
   `INVOKE_TASKLIB_TEST_XDOCTEST=false` turns the option **on**, and a bad integer is a Python
   traceback (1.1). Same family as the `CI=false` bug that was fixed.
2. `clean.all` removes the `site_dir` of the mkdocs config even when it is outside the project
   (1.2).
3. Running `inv` from a subdirectory finds `invoke.yaml` but runs everything relative to the
   current directory (1.3).
4. `cov_reports` rejects the most common pytest-cov syntax, `term-missing:skip-covered` (1.5), and
   `security.audit` does not audit the extras (1.7).
5. Design: the shell parser behind `check_program` is the most complex code of the repository and
   serves no task (2.1); one capture helper for the hidden commands (2.2).

## What happened to the previous review

Done and verified on the current code: the `CI=false` confirmation (`_in_ci`), the release-candidate
tag sort (`_last_version_tag` compares numbers), `clean` and `docs/site` (`_read_site_dir`), the
accent loss in ASCII mode, the shell keywords and `~/` in `check_program`, `check.cov`, the
`UV_PUBLISH_TOKEN` fallback for `--test-pypi`, the artifacts checked by `release.build`, the
`skip_missing` of `test.all`, the confirmation of `env.create-venv`, the layering leaks (`find_tool`,
`split_args`, `not_found_message`, `config/_resolve.py`), the `find | xargs` pipeline (`_files.py`),
keyword-only options (all 40 tasks), `report_failure`, the pinned `uvx` tools, `tasklib.test.timeout`,
the removal of `invoke_tasklib.ns`, the `architecture.md` gaps, the lines over 100 columns and
`E501`, the sdist, the classifiers, `pytest-benchmark`, the Windows warning, and the nightly job.
The step registry (`Step`) exists but is only half of what 2.1 asked for (see 2.3).

Still open from before: the namespace and module names (2.6), `imports.check-isolated` (2.7), the
`raises` plus `assert` tests (4.1), the property tests (4.3).

## 1. Bugs and defects

### 1.1 Boolean and integer environment variables are cast wrongly — medium **[verified]**

`make_ns` registers `default_config()` so that Invoke reads `INVOKE_TASKLIB_<SECTION>_<KEY>`.
Invoke casts the variable to the **type of the default**, and for a boolean it does
`new not in ("0", "")` (`invoke/env.py:_cast`):

```text
$ INVOKE_TASKLIB_TEST_XDOCTEST=false inv config.show | grep xdoctest
    xdoctest: true  # environment variable INVOKE_TASKLIB_TEST_XDOCTEST
$ INVOKE_TASKLIB_TEST_UNIT_TIMEOUT=abc inv config.show
    return old.__class__(new)
ValueError: invalid literal for int() with base 10: 'abc'
```

So `false`, `no` and `off` all mean `true` for `test.xdoctest`, `test.timeout` and `check.cov`, and a
bad integer for the three timeouts ends in a traceback, not in the one-line exit-2 message that
`load_config` gives for every other invalid value. `_int_from_text` already handles the same problem
for `cov_fail_under`, the one integer with no default.

Suggestion: register the booleans and integers with a default of `None` in `default_config()` (Invoke
then keeps the string as it is; the real defaults stay in `SCHEMA`). Parse the text in
`_validate_bool` (`true/false/1/0/yes/no/on/off`, case-insensitive, strings only) and in `_validate_int`
(extend `_int_from_text` to every integer key). `config.show` still reports the variable as the
origin. Tests: parametrize `"false"`, `"0"`, `"no"`, `"true"`, `"abc"` through `get_config` with a
`Config` that has the variable in `_env`, and one integration test with the real `inv` and a real
environment variable. Document the accepted spellings in `uguide/config.md`.

### 1.2 `clean.all` removes a `site_dir` outside the project — medium **[verified]**

`_site_dirs` returns `config.parent / site_dir`. An absolute `site_dir`, or one with `..`, is used
as it is:

```text
$ cat docs/mkdocs.yml        # in a probe project
site_dir: /…/scratchpad/outside
$ inv clean --dry-run | grep -i outside
🗑️  Would remove /…/scratchpad/outside
```

The `keep_tracked` check does not protect it: git does not track anything outside the repository, so
`git ls-files` fails, `_has_tracked_files` is `False`, and `shutil.rmtree` would run. A shared build
directory (`site_dir: /var/www/docs`, `../public`) is plausible in a real mkdocs config, and a
cleanup task should never leave the project.

Suggestion: in `_site_dirs`, resolve the path and keep it only if it is inside `Path.cwd()` and is
not the cwd itself; otherwise `say` a `⏭️ Not removing …: outside the project` line. Apply the same
test in `_remove_dir`, so every caller is covered. Tests: absolute path, `../x`, `.`, and a symlink
that points outside.

### 1.3 `inv` run from a subdirectory mixes two roots — medium **[verified]**

Invoke looks for `tasks.py` in the parents of the cwd, and loads the `invoke.yaml` next to it, but it
does not change directory. Every path of the library (`Path("tests/unit")`, `Path("pyproject.toml")`,
`src/<pkg>`, `git` commands, `dist/`) is relative to the cwd:

```text
$ cd sub && inv test.unit
⏭️  No 'tests/unit' directory: skipping unit tests
$ cd sub && inv config.show | grep -E "name:|src:"
    name: demo  # project file          <- found in ../invoke.yaml
    src: src/demo  # derived            <- looked up in ./src/demo
```

Skipping the tests with a `⏭️` line is the worst outcome: `check.all` passes while nothing ran.
`release.publish` reads `pyproject.toml` and `git status` of the wrong place in the same way.

Suggestion, smallest first: (a) in `load_config`, exit with a message when the cwd is not the directory
of the loaded project file ("run inv from the project root, or pass --search-root"); or (b) have
`make_ns` store the directory of the calling `tasks.py` (`sys._getframe`/`inspect`, or an explicit
`make_ns(root=Path(__file__).parent)`), and let `runner.run` and the file helpers use it (`c.cd(root)`,
`root / path`). (a) is a few lines and prevents the silent skip; (b) is the real fix and is
**[breaking]** for code that calls the helpers with relative paths.

### 1.4 A failure inside a nested task is reported twice — low **[verified]**

`env.create-venv` and `env.update` call the task `install` inside their own `report_failure`. A failure
of `uv sync` prints both titles:

```text
$ inv env.create-venv --yes        # with a uv that fails on `sync`
❌ Failed: Installing project dependencies
❌ Failed: Creating virtual environment
```

`test.doctest` does not have the problem (two sequential tasks). Suggestion: split `install` into a
plain `_install(c, …)` function that the two callers use without a second `report_failure`, or mark
the exception in `report_failure` (`exc.add_note("reported")`, tested with `getattr`) so an outer block
does not repeat it. The first is simpler and keeps `Exception` untouched.

### 1.5 `test.cov_reports` rejects the usual pytest-cov syntax — medium **[verified]**

`_validate_cov_reports` checks each word against `COV_REPORTS`, so:

```text
>>> _validate_cov_reports("term-missing:skip-covered")
ValueError: Unknown coverage report ['term-missing:skip-covered'] in 'tasklib.test.cov_reports'. …
>>> _validate_cov_reports("html:cov_html")        # same error
>>> _validate_cov_reports([])                      # accepted: ()
```

`term-missing:skip-covered` is the most used value of `--cov-report`, and `html:<dir>` / `xml:<path>`
are how a project moves the reports (which also decides where `coverage_report` and `clean` look, see
1.9). The JSON schema has the same closed `enum`, so an editor flags the valid value too.

Suggestion: validate the part before the first `:` against `COV_REPORTS`, keep the full string, and
relax the schema to `pattern` (`^(html|xml|…)(:.+)?$`). Reject an empty list like `check.tasks` does
(or document that it gives pytest-cov's own default). Quote each value in the command (`build_command`
already would, but `_run_pytest` joins with `" ".join(cmd)` before `build_command`, so a value with a
space or `$` is not quoted, see 1.9).

### 1.6 Tags like `v1.2.0-backport` are taken for pre-releases — low **[verified]**

`_PRERELEASE_PATTERN` is `[-._]?(a|b|c|rc|alpha|beta|pre|preview|dev)\d*` used with `match`, with
nothing after the keyword. Any suffix that **starts** with `a`, `b` or `c` matches:

```text
_parse_release("1.2.0-backport") -> ('1.2', True)
_parse_release("1.2.0-cool")     -> ('1.2', True)
_parse_release("1.2.0-alpine")   -> ('1.2', True)
_parse_release("1.2.0.post1")    -> ('1.2', False)      # correct
```

`doc.publish-latest` then prints `Skipping the pre-release version` and publishes nothing, which is the
same symptom as the old rc bug. Suggestion: require the keyword to be followed by digits or the end
(`(?:a|b|c|rc|alpha|beta|pre|preview|dev)(?:\d+)?$` on the whole `rest`, or `(?![a-z])`), and add the
three tags above as parametrized cases.

### 1.7 `security.audit` does not audit the extras — medium **[verified in the uv help]**

The command is `uv export --locked --no-emit-project --no-hashes --all-groups`. In uv the optional
dependencies are opt-in (`--extra`, `--all-extras`), so the packages that only an extra installs are
never given to `pip-audit`, whereas `env.install` installs them (`--all-extras`) and users run them.
This repository has no extra, so its own audit hides nothing; a project with `[project.optional-
dependencies]` is only partly audited and gets a green result. Add `--all-extras`; test the command
list; mention it in `uguide/security.md`.

### 1.8 `integration --cov` and `functional --cov` always append — low **[reading]**

Both pass `append=True`, so `inv test.integration --cov` run alone adds to whatever `.coverage` the
last run left. The percentage and the `--cov-fail-under` check then include stale data, and a coverage
drop can go unnoticed. The sequence `unit --cov` then `integration --cov` in CI needs the append, so
make it explicit: a `--append` flag (default `False`), with the CI workflow and `uguide/test.md`
passing it; or run `coverage erase` in `test.unit --cov` only, which starts the series.

### 1.9 Minor

- `clean` removes `htmlcov` and `.coverage_html` only, whereas `coverage_report` honours
  `[tool.coverage.html] directory` through `_coverage_html_dir`. Use the helper in `clean` too
  **[reading]**.
- `_run_pytest` joins `--cov-report {report}` and `--timeout …` into a string before `build_command`,
  which only quotes the user's `args` and `paths`; a configured value is never quoted. All the current
  values are safe words, so this is latent, but `cov_reports` of 1.5 would make it real **[reading]**.
- `_requires_python_lower_bound` ignores `>3.10` (no `>=`) and falls back to the hard-coded
  `DEFAULT_PYTHON_VERSION = "3.14"`, which has to be edited every year and may be a version the
  project does not support. See 2.5 **[reading]**.
- `_steps.run_step` catches `Exit` and `UnexpectedExit` only; any other exception (a bug, an
  `OSError`) ends a `--keep-going` run without the summary. Catch `Exception`, report its type and
  message as the reason, and let `KeyboardInterrupt` through **[reading]**.
- Tools that capture output (`git status`, `git ls-files`, `_discover`) do not set `pty=False`. Under a
  terminal, `run` turns the pty on and merges stderr into stdout, so a Python warning on stderr of
  `_discover` would be read as a module name **[reading]**. See 2.2.

## 2. Design

### 2.1 The shell parser of `check_program` serves no task — medium **[verified by grep]**

About 190 lines of `runner.py` (`_stages`, `_strip_assignments`, `_program_of`, `_SEPARATORS`,
`_SHELL_KEYWORDS`, `_WRAPPERS`, `UNCHECKED_PROGRAMS`, the `xargs` branch) and a large share of the
857 lines of `test_runner.py` parse shell grammar: pipelines, `&&`, subshells, `xargs`, `sudo`,
`time`. No command built by a task uses any of it since `find | xargs` went away (`grep` finds no
`|`, `&&`, `;` or `xargs` in a command of `src/`; `find` is still in `UNCHECKED_PROGRAMS` for nothing).
The cost is not only size: the parser still gets quoted data wrong,

```text
>>> check_program("ls ';' foo")
Exit: 'foo' was not found on the PATH.          # ';' is a quoted argument, not a separator
>>> check_program(build_command("ls", args="-k ';' x"))
Exit: 'x' was not found on the PATH.
```

because `shlex` drops the quotes before `_stages` compares the token with `";"`.

Suggestion **[breaking for custom tasks]**: check the first word only (after `NAME=value`
assignments), which is what the tasks build, and say in the docstring and in
`uguide/custom_tasks.md` that `run(..., check=False)` is the way to run a pipeline. The `python -m
<module>` and pytest-plugin checks stay (they are the useful part, and they do not need the parser).
Alternative: make the checked programs explicit, `run(c, cmd, needs=("shellcheck",))`, which is also
what `_steps.Step.programs` already declares. Either way, delete about half of `runner.py` and its
tests, and the false positive above.

### 2.2 One helper for commands whose output is read — low **[reading]**

Six places read the output of a command with `hide=True` plus a mix of `echo=False`, `pty=False` and
`warn=True` (`doc.py` twice, `release.py` twice, `clean._has_tracked_files`, `imports.check_isolated`),
and they disagree about `pty=False` (1.9). Add `runner.capture(c, command, *, warn=False) -> Result`
that sets `hide=True, echo=False, pty=False`. The reading call sites shrink, the pty merge cannot
happen, and the unit tests of those tasks can assert one kwarg set (`run_kwargs`) instead of six.

### 2.3 The step registry is half done — low **[reading]**

`Step(task, programs, modules)` removed two lists, but a new `check.all` step still means editing
`CHECK_STEPS` (`_constants`), the default string in `_schema.py`, `check.STEPS`, `env.TOOL_PROGRAMS` /
`TOOL_MODULES`, and `runner.PROGRAM_HINTS` / `PROGRAM_GROUPS` (`architecture.md` lists the four
steps; tests keep them in line). Two cheap improvements:

- `check._missing_tools` has `if step == "unit"` twice (`xdoctest`, `pytest_timeout`), so the registry
  does not say what the `unit` step needs. Let `Step.modules` be a `tuple[str, ...] | Callable[
[TasklibConfig], tuple[str, ...]]`; `fix.py` needs nothing. `_missing_tools` and its special cases
  go.
- The default `check.tasks` is a comma-separated string in `_schema.py` that repeats the first six
  names of `CHECK_STEPS`. Put `DEFAULT_CHECK_STEPS` in `_constants.py` and derive the string, so the
  order cannot drift (same for `fix`).

### 2.4 File selection ignores `.gitignore` and excludes by name at any depth — low **[reading]**

`find_files` skips the directories named in `EXCLUDED_DIRS` (`.venv`, `.git`, `.pytest_cache`,
`node_modules`) and, for markdown and shell, `build`, `dist`, `site`, `htmlcov`, … **at any depth**:

- `src/pkg/build/README.md` or a `src/pkg/site/` package is skipped silently by
  `test.doctest-markdown` and the shell tasks;
- a virtual environment named `venv` or `env`, `.tox`, `.nox` or `.direnv` is walked for `*.sh`
  (shellcheck on thousands of third-party scripts), because only `.venv` is excluded for shell.

`ruff`, `codespell` and `pre-commit` all follow `.gitignore`. Suggestion: `find_files` lists
`git ls-files -co --exclude-standard -- '*<suffix>'` when the cwd is a git work tree, and falls back
to the walk with the current exclusions otherwise. One policy for all the tasks, and no list to
maintain. `EXCLUDED_DIRS` can then leave `config/_constants.py`, where it does not belong (it is not
a config constant; `_files.py` and `clean.py` import it from the config package).

### 2.5 `package.python_version` duplicates what uv already does — low **[reading] [breaking]**

`_derive.py` (three functions, a regex, a hard-coded default) computes a version from
`.python-version`, then `requires-python`, then `"3.14"`, only to give it to `uv venv --python`.
`uv venv` already reads `.python-version` and the project's `requires-python`. Make `python_version`
optional (`None` = let uv choose), pass `--python` only when it is set, and drop `_derive`'s Python
part, `DEFAULT_PYTHON_VERSION`, `REQUIRES_PYTHON_LOWER_BOUND` and `PYTHON_VERSION_PATTERN`'s use as a
fallback. This also ends the "default must be updated every year" chore and the `>3.10` case of 1.9.
Check first that the `uv` version you support gives the same result on the three layouts.

### 2.6 Namespace names and `configuration.py` — low **[breaking]**

Open since the review before last. `formatting`/`typecheck`/`testing` are exposed as
`format`/`types`/`test` through the `_MODULES` dict, and a hand-made collection needs the workaround in
the docstring of `__init__.py` (`Collection.from_module(testing, name="test")`). `configuration.py`
(task `config.show`) sits next to the package `config/` and the namespace `config`. Suggestion: a
`NAMESPACE = "test"` constant in each task module, read by `make_ns` and documented for
`Collection.from_module(module, name=module.NAMESPACE)`; rename `configuration.py` (for example
`show.py`). Do it in the same release.

### 2.7 `imports.check-isolated` — low **[reading]**

Open since the previous review: it starts one interpreter per module and echoes one command per
module (300 lines for a 300-module package). One worker (`python -m invoke_tasklib._discover
--import-each`) that imports each module in a fresh subprocess and prints one summary line plus the
failures would be as strict and far quieter. It is also not a `check.all` step.

### 2.8 `runner.py` does three jobs — low **[reading]**

591 lines for: running a command (`run`, `build_command`, `split_args`, `python_executable`), finding
tools (`find_tool`, `check_program`, `_check_module`, `_check_plugin_options`), and install advice
(`PROGRAM_HINTS`, `PROGRAM_GROUPS`, `PLUGIN_OPTIONS`, `hint`, `not_found_message`). After 2.1 the middle
part is small. Move the hint tables and the lookups to `tools.py` and keep `runner.py` as the entry
point, re-exporting nothing. `PROGRAM_GROUPS` mixes program names (`ruff`) and module names
(`pytest_timeout`) in one dict; two dicts would remove the guess.

### 2.9 Two ways to detect CI — low **[reading]**

`lint.check_python` switches to `--output-format=github` on `GITHUB_ACTIONS == "true"`;
`release.publish` uses `CI` through `_in_ci()`, and `trusted` on `GITHUB_ACTIONS` plus
`ACTIONS_ID_TOKEN_REQUEST_URL`. The two are both correct, but a helper `runner.in_ci()` and a
`runner.in_github_actions()` (documented once) would keep the rules (1.1 of the previous review) in one
place and testable once.

## 3. Documentation

- **`CLAUDE.md` is stale on the layout [verified by grep]**: it says `__init__.py` of `config/` holds
  `get_config` and `load_config` (they are in `config/_resolve.py`), lists `config/` without
  `_resolve.py` and `__main__.py`, and says "Three private modules support the tasks" without
  `_files.py`. An agent will look for the functions in the wrong file.
- **`architecture.md`** has no `_files.py` (`grep` finds no mention) while it documents `_steps.py`,
  `_graph.py` and `_discover.py`.
- After 1.1, 1.3 and 1.5 update `uguide/config.md` (accepted boolean spellings, the working
  directory, the `cov_reports` syntax) and `troubleshooting.md` (the subdirectory case).
- The README, `docs/docs/index.md` and `uguide/index.md` task tables and `docs/docs/schema.json` are
  guarded by tests; keep them. If the schema of 1.5 changes, regenerate with
  `python -m invoke_tasklib.config`.

## 4. Tests

Strengths: 2,506 tests in 13 s, 100% line and branch coverage, a real integration suite (mkdocs/mike,
git, quoting, a stripped `PATH`, real `inv`), `filterwarnings = error`, and the `match=` rule applied
almost everywhere.

### 4.1 One `raises` plus an assert in the same test — low **[verified]**

`CLAUDE.md`: "a test has one `assert` or one `pytest.raises`". The `ast` scan finds **75** tests
(61 in the previous review) that have a `pytest.raises` followed by an `assert` on the caught
exception, nearly always `info.value.code`:

```python
with pytest.raises(Exit, match="...") as info:
    task(c)
assert info.value.code == 127
```

The number grows with each PR, so the rule and the suite disagree. Pick one: a helper in
`tests/helpers.py`, `exit_code(fn, *args, **kwargs) -> int`, that wraps the `raises` and returns the
code (the test becomes `assert exit_code(...) == 127`, and a second test checks the message); or amend
`CLAUDE.md` ("one `raises` may be followed by assertions on the caught exception"). The second is one
line and describes the suite; the first is stricter. No other test has two `assert`s.

### 4.2 Small rule violations — low **[verified]**

- Three `raises`/`warns` have no `match=`: `tests/unit/config/test___main__.py::
test_running_the_module_exits_with_code_0` and `tests/unit/test__discover.py::
test_running_the_module_exits_with_the_exit_code` (`pytest.raises(SystemExit)`), and
  `tests/unit/test_init.py::test_make_ns_blames_the_caller_on_windows`
  (`pytest.warns(RuntimeWarning)`). `SystemExit` has no message, so `match=r"^0$"` on the code string
  is the way, and the warning needs the text.
- One test has a `for`: `tests/integration/test_doc.py::
test_last_version_tag_returns_the_highest_release` creates the tags in a loop. Make the tags a
  fixture parameter or one `git tag a b c` call.
- Four tests have neither an `assert` nor a `raises` (`test_env.py::test_create_venv_dry_run_does_not_ask`,
  `test_check_tools_does_not_need_the_config`, `test_init.py::
test_warn_if_unsupported_platform_is_silent_on_posix`, `test_release.py::testpypi_token`). The
  first three pass by not raising, which is legitimate but is better as an explicit assertion on the
  recorded commands or on `recwarn`; the last is a fixture that the scan took for a test.
- `_context` is defined in 13 test modules while `tests/helpers.py` has `make_context`, `commands` and
  `run_kwargs`. Most of the copies differ by one default; use the helper and keep a module-level
  `_context = partial(make_context, …)` only where the default differs.

### 4.3 Missing tests — medium

- Each of 1.1 to 1.7 with its regression check (`git stash push src`). For 1.1 and 1.3 add an
  integration test with the real `inv` (the unit test with `MockContext` cannot show that Invoke
  casts the variable).
- Property tests for the two modules with real algorithms: `shlex.split(build_command(...))`
  round-trips the words, and `find_cycles` agrees with a brute-force reachability on small random
  graphs from `default_rng(0)`. `grep` finds no `hypothesis` or `default_rng` in `tests/`.
- A test that every task which reads a file or a directory is called with the project root as cwd
  (after 1.3), so the silent `⏭️` skip cannot come back.

### 4.4 No benchmarks: `test.benchmark` is nightly but skips an empty directory — medium **[verified]**

`tests/benchmarks/` does not exist, so the nightly `ci-benchmark.yaml` runs `inv test.benchmark`,
prints `⏭️ No 'tests/benchmarks' directory`, and passes. The job, the `pytest-benchmark` dependency and
the task all exist, and nothing is measured. The library has parts whose cost can regress without a
test failing, and `coola` shows the pattern to copy (read from its GitHub tree and nightly workflow,
not run here):

- `tests/benchmarks/` with a `conftest.py` and one file per area, named `test_<area>_benchmark.py`;
- a nightly workflow that restores the previous `.benchmarks` JSON from the last successful run,
  runs `pytest --benchmark-only --benchmark-compare --benchmark-compare-fail=mean:50%` (a loose
  threshold, because the runners are noisy), and uploads `.benchmarks` as an artifact;
- a script (`dev/benchmark_trend.py --days 90 --prune`) that writes a trend table to the job summary
  and deletes results older than 90 days.

What to benchmark here (the hot paths are pure Python, so the numbers are stable):

- `_graph`: `import_graph` and `find_cycles` on a generated graph of 1,000 and 10,000 modules (a
  chain, a dense DAG, one large cycle). `_Tarjan` is iterative so the size is the point;
- `runner`: `build_command` with many paths, and `check_program` (more so if 2.1 changes it);
- `_files.find_files` and `testing._find_markdown_files` on a generated tree in `tmp_path` (and the
  `git ls-files` variant of 2.4, to justify the change with numbers);
- `config`: `get_config` on a full config, since every task calls `load_config`;
- `output.say` with the ASCII conversion, and `make_ns()` (called on every `inv` start, and it
  builds 13 collections: the start-up time of every project that uses the library);
- `import invoke_tasklib` time (`coola` has `test_import_benchmark.py`, excluded from the nightly run,
  as a separate measure): it imports all 13 task modules eagerly.

Steps: add `tests/benchmarks/` with `conftest.py` and these files; build inputs with `default_rng(0)`
(`CLAUDE.md`); copy the compare/artifact/prune steps into `ci-benchmark.yaml`, and port
`benchmark_trend.py` into `dev/`; add the benchmarks to `uguide/test.md` as the example of a
`paths.benchmarks` layout. A benchmark is not a unit test, so keep it out of `testpaths` runs
(`pytest-benchmark` runs the functions once without `--benchmark-only`, which is fast enough, but
set `--benchmark-disable` in the default `addopts` so `inv test.unit` pays nothing). Also decide
whether `test.benchmark` should exit with a non-zero code when the directory is missing and the
task is run explicitly (today it cannot tell "no benchmark yet" from "forgot to add one").

## 5. Packaging, config, CI

- **CI hygiene [verified by grep]**: every workflow has a top-level `permissions:` block and every
  `uses:` is pinned to a 40-character SHA. Keep it.
- **What CI runs [verified by grep]**: `inv test.all --cov`, `inv test.unit --cov`, `inv test.doctest`,
  `inv test.benchmark`, `inv lint.check-python`, `inv format.check-python`, `inv types.check`,
  `inv imports.check-cycles`, `inv release.build --check`, `inv security.audit`,
  `inv check.all --keep-going --only …` (nightly), and the docs publishing. `format.check-docstrings`,
  `format.check-shell`, `lint.check-spelling` and `imports.check-isolated` are covered by pre-commit
  or by the nightly job only; `check.all` with its default steps is never run by a pull-request job,
  so a break of the composite task (a renamed step, a wrong tool list) is found a day late. A
  pull-request job `inv check.all --keep-going` with the default steps would run the product the way
  a user does, in about the time of the separate jobs.
- **Version**: `0.1.0a0` with `Development Status :: 3 - Alpha`. The breaking items above (1.3b, 2.1,
  2.5, 2.6) belong to one `0.2.0` or to the `0.1.0` release, announced in the notes.
- **`feu[all]`** in the `dev` group is only used by `dev/generate_versions.py`; check that it
  needs to be in the `dev` group of every contributor **[reading]**.

## 6. Suggested order of work (one PR each, as in `CLAUDE.md`)

1. Environment variable casting (1.1) + tests, then the documentation line.
2. `clean` stays inside the project (1.2); `_coverage_html_dir` in `clean` (1.9).
3. The working-directory guard (1.3a), then the real root if wanted (1.3b).
4. `cov_reports` syntax (1.5) with its schema, `--all-extras` (1.7), the pre-release regex (1.6).
5. Nested failure line (1.4) and the `run_step` exception scope (1.9).
6. `runner.capture` (2.2) and the `Step.modules` callable (2.3).
7. The simplification of `check_program` (2.1) and the split of `runner.py` (2.8).
8. `CLAUDE.md` and `architecture.md` (section 3); test rules (4.1, 4.2); missing tests (4.3).
   Benchmarks (4.4) can go in parallel, and before 2.1, 2.4 and 2.5 to measure them.
9. File selection (2.4), `python_version` (2.5), `append` flag (1.8).
10. As one release: namespace names (2.6), `check-isolated` (2.7).

## What was and was not done

- Done: all of `src/` was read; the baseline ran (`pytest`, coverage, `ruff`, `ty`); 1.1 to 1.6, the
  `uv export` default of 1.7 and the false positive of 2.1 were reproduced with the real `inv`, a probe
  project and `python` snippets (kept outside the repository); the tests were scanned with `ast`; the task
  signatures were listed from a real `make_ns()`; the workflows were searched.
- Not done: no source file or test was changed. Items marked **[reading]** were not run and need a
  second look before a PR; in particular 1.8 (no `.coverage` experiment), 2.4 (`git ls-files` options)
  and 2.5 (the `uv venv` behaviour without `--python`) must be tried on the supported `uv` versions.
  `release.publish` was not run, nothing was uploaded, the workflows were not read in full and CI
  results were not looked at.
