# Review of `invoke-tasklib` — suggestions

This review replaces the previous one (`90898bd`, #153). Most of what it asked for has been done
since (integration tests, the doctests, quoting, `import_name`, `check.all`, the config `SCHEMA`,
...), so the review was redone on the current code. The old text stays in the git history.

## Scope and method

Everything that matters for the behaviour of the library was read, not skimmed:

- `src/invoke_tasklib/`: all 16 modules (4,362 lines);
- `tests/`: the layout, the helpers, the integration tests of the runner and of `check`, and the
  whole tree searched for the rules of `CLAUDE.md`;
- `pyproject.toml`, `invoke.yaml`, `tasks.py`, `.pre-commit-config.yaml`, `dev/`;
- the docs (`troubleshooting.md`, `custom_tasks.md`, `architecture.md`, `mkdocs.yml`), the README,
  `.github/` (`ci.yaml`, `ci-test.yaml`, the composite actions; pinning and permissions of every
  workflow were grepped).

`.make/` (vendored) and the other pages of `docs/` were not read line by line.

Baseline on `main` (`f5a3933`, nothing modified except this file):

- `pytest tests`: 1329 passed, 100% line and branch coverage;
- `ruff check`, `ty check`: clean;
- `inv test.doctest`: 69 + 42 markdown files passed;
- CI was not looked at (not assessable from here).

Legend: **[verified]** reproduced here with the real tools or a probe script; **[reading]** found
by reading the code, not run. Severity: high / medium / low. **[breaking]** changes a public
behaviour or signature (allowed by the request).

## Summary: what to do first

1. `check.all --keep-going` throws away the "tool not found" message (1.1). One-line fix.
2. Make the missing-tool messages explicit and correct everywhere (section 1): wrong hints for
   `git`, `uvx`, `pre-commit`, `docformatter`, `ruff`, `ty`; no message at all for missing pytest
   plugins; false "not found" for `FOO=1 cmd`.
3. Add a pre-flight check (`env.check-tools` and a pre-flight in `check.all`) that lists **every**
   missing tool at once (1.6).
4. Fix the small bugs of section 2 (wrong count of markdown files, `EOFError` in `release.publish`,
   `?` in place of the emojis).
5. Then the design items of section 3 (a `fix.all`, `clean --dry-run`, split of `config.py`,
   renaming the modules, one token per index).

## 1. Missing tools must give an explicit message

The runner already has `check_program` and `PROGRAM_HINTS` (good design). The gaps below are the
places where a missing tool is still silent, wrong or lost.

### 1.1 `check.all --keep-going` drops the message — high **[verified]**

`_run_step` (`check.py`) catches `Exit` and returns its message, but `all_` only tests
`is not None` and never prints it:

```text
$ PATH=/usr/bin:/bin inv check.all --keep-going --only lint,types
🔎 Running all the checks...
🔍 Checking code linting with ruff...
❌ Failed: Checking code linting with ruff
❌ Step failed: lint
...
2 of 2 check(s) failed: lint, types
```

Without `--keep-going` the same run prints
`'ruff' was not found on the PATH. Install the project tools with ...`. With it, the user only
learns that the step failed, and the reason (here: the missing tool) is gone. The same happens to
every `Exit` message of a task (invalid config, missing `mkdocs.yml`, ...).

Suggestion: print the message of the failure under the `❌ Step failed:` line, and repeat the
reasons in the final summary:

```text
❌ Step failed: lint
   'ruff' was not found on the PATH. Install ...
```

Tests to add: one unit test with a `Mock` that raises `Exit("boom")` and a check that `boom` is in
the output; one integration test with `PATH=/usr/bin:/bin` (like `tests/integration/test_runner.py`)
that checks the hint of the tool is printed with `--keep-going`.

### 1.2 Several hints are wrong or missing — medium **[verified]**

`_hint("git")` and `_hint("uvx")` return the default hint (`invoke env.install`), which cannot
install them (`git` is a system tool, `uvx` comes with `uv`). The same default is given for
`pre-commit`, `docformatter`, `ruff`, `ty`, `pyright`, `mkdocs`, `mike`, `pip-audit` and
`coverage`, where it is right only if the project has the `dev`/`docs` groups.

Suggestions:

- Add `git` (system package manager / `xcode-select --install`), `uvx` (same hint as `uv`),
  and `pre-commit`.
- Make the default hint say **which group** has the tool, from a table next to `PROGRAM_HINTS`:

  ```text
  ruff, ty, pyright, docformatter, codespell, pre-commit, pytest, coverage -> group dev
  mkdocs, mike                                                             -> group docs
  ```

  The message becomes `'mike' was not found. Install it with the 'docs' group: uv sync --group docs`
  and takes `tasklib.groups.*` into account.

- Test that every program built by a task has an explicit entry: a unit test that collects the
  first word of every command recorded by `MockContext` over all the tasks, and checks it is in
  `PROGRAM_HINTS` or in `UNCHECKED_PROGRAMS`. A new tool then cannot be added without a hint.

### 1.3 A missing pytest plugin gives pytest's own error — medium **[reading]**

`_check_module` only checks `python -m pytest`. The tasks also rely on plugins through options:
`--xdoctest` (`xdoctest`), `--timeout` (`pytest-timeout`), `--cov*` (`pytest-cov`),
`--benchmark-only` (`pytest-benchmark`, which is not even in the `dev` group of this repo), and
`python -m coverage`. If one is missing, pytest says `error: unrecognized arguments: --xdoctest`,
which does not say what to install. `check.all` and `test.unit` are the first tasks a new user
runs.

Suggestion: `run(..., requires=("xdoctest",))` (or a small `PLUGIN_OPTIONS` table: option -> module
and package name), checked with `importlib.util.find_spec` before the command, with the message
`The option --xdoctest needs the pytest plugin 'xdoctest': add it to the dev group`.

### 1.4 `python -m <module>` is only checked for the running interpreter — low **[reading]**

`_check_module` returns when `words[0] != sys.executable`. A custom task that runs `python -m foo`
(the documented way to write one) falls back to Python's `No module named foo`. Either check the
module with the interpreter that will run (`python -c "import importlib.util..."` is too slow) or
document the limit in `custom_tasks.md`.

### 1.5 `check_program` rejects valid shell commands — medium **[verified]**

`check_program` splits the command with `shlex` and looks the first word of every stage up with
`shutil.which`. Verified with a probe:

- `FOO=1 ruff check` -> `'FOO=1' was not found on the PATH`;
- `VAR=$(date) ls` -> `'VAR=$' was not found`;
- `(ls)` -> `'(' was not found`;
- `cd docs && ls` passes only because macOS has `/usr/bin/cd`; on Debian/Ubuntu `cd` is a shell
  builtin with no executable, so it fails there **[reading]**.

`run` is the public API for custom tasks (`custom_tasks.md`), and the error is a wrong "tool is
missing" message, which is worse than none. Suggestions: skip leading `NAME=value` words, add the
shell builtins (`cd`, `export`, `test`, `[`, `exec`, `source`, `.`, `:`) to `UNCHECKED_PROGRAMS`,
and skip a stage that starts with `(`, `{` or `$(`. Add a `check=False` argument to `run` for the
cases where the caller knows better.

### 1.6 No way to see all the missing tools at once — medium

Today the first missing tool stops the task, the user installs it and finds the next one.
`check.all` needs `ruff`, `docformatter`, `ty`, `pytest` plugins, and `--only docs` needs
`mkdocs`. Suggestions:

- A task `env.check-tools` (read-only): one view of the tools that the tasks run. Requested
  by the maintainer; the design is in 1.6.1.
- A pre-flight in `check.all`: before running the selected steps, compute the programs of those
  steps (a `PROGRAMS` dict per step, next to `STEPS`) and report all the missing ones in one
  message, instead of running 20 s of formatting before failing on `ty`.
  With `--keep-going` the pre-flight should still run and list the steps that cannot run.

#### 1.6.1 Design of `env.check-tools`

**Goal**: answer "is `ruff`, `pyright`, ... available?" with a single command, before running
anything. Suggested behaviour:

- **Name and location**: `env.check-tools`, function `check_tools` in `env.py`. It follows the
  rule `check_<target>` never modifies anything, and it sits next to `show-python-config`.
- **What is checked**: two closed lists, declared once as module constants.
  - Programs, looked up with `shutil.which`: `uv`, `uvx`, `git`, `ruff`, `ty`, `pyright`,
    `docformatter`, `codespell`, `pre-commit`, `shellcheck`, `shfmt`, `mkdocs`, `mike`.
  - Python modules of the running interpreter, looked up with `importlib.util.find_spec`:
    `pytest`, `coverage` and the plugins the test tasks pass options to (`xdoctest`,
    `pytest_timeout`, `pytest_cov`).
- **Output**: one line per tool, the path when it is found, the install hint when it is not, all
  tools listed (no stop at the first one):

  ```text
  ✅ ruff: /project/.venv/bin/ruff
  ❌ shfmt: program not found. Install shfmt with your system package manager, ...
  ```

- **Exit code**: 127 (the code already used for a missing program) with the message
  `12 of 18 tool(s) missing: uv, ruff, ...` when something is missing, 0 otherwise. A CI job can
  use it as a gate.
- **No config needed**: it does not call `load_config`, so it works before `invoke.yaml` exists;
  this is when a new contributor needs it most.
- **No side effect**: it runs no subprocess (no `--version`), so it is instant and cannot hang;
  it installs nothing (`env.install` does that).
- **Hints**: reuse `PROGRAM_HINTS` and `DEFAULT_HINT` of `runner.py`; the improvements of 1.2
  (hints for `git`, `uvx`, `pre-commit`, the group table) then apply to this task for free.

Possible extensions, not needed for a first version:

- `--only`/`--group` to restrict the list (`dev`, `docs`, `shell`), and `--json` for scripts.
- Derive the lists from the tasks instead of declaring them: the `PROGRAMS` per step of the
  `check.all` pre-flight (1.6) and the test of 1.2 (every program built by a task has a hint)
  would keep the list in sync, so a new tool cannot be added to a task and forgotten here.
- Report the version (`ruff 0.16.1`) through `importlib.metadata` for the modules, and an opt-in
  `--versions` for the programs.

Tests to write (one behaviour each): `_find_tool` for a program and a module, found, missing and
a module with no origin; the whole output when everything is available and when one program or one
module is missing; the message and the exit code 127; all the missing tools are listed; the module
is looked up as a module; no command is run; no config is needed; every program of
`PROGRAM_HINTS` is in the list. Integration (no patching): real lookups of a program and of a
module, and the task run in a subprocess with `PATH=/nonexistent`, checking the output, the code
127 and that it works without an `invoke.yaml`.

Docs to update (rule of `CLAUDE.md`): the README task table, `docs/docs/index.md`,
`uguide/index.md`, a section in `uguide/env.md`, the `invoke --list` sample of `get_started.md`,
and a sentence in `troubleshooting.md` (the "command not found" entry).

**Status**: a prototype of this design was written in the working tree on the branch
`feat/add-check-tools` before the decision to only document it. It is not committed and not in a
PR; it can be reviewed or discarded.

### 1.7 Messages go through `Exit`, so they depend on invoke's formatting — low **[reading]**

`say` writes to stdout, `Exit` messages are printed by invoke on stderr. `❌ Failed:` lines are on
stdout while the reason is on stderr, so `inv ... 2>/dev/null` shows a failure with no reason, and
the two interleave in a CI log. Send the `❌` lines (and `⏭️` skips) to stderr, or print the
failure reason in `step` itself.

## 2. Bugs and small defects

### 2.1 `test.doctest-markdown` reports the wrong number of files — low **[verified]**

`inv test.doctest-markdown --paths README.md` prints `Found 42 markdown files` and
`All 42 markdown files have been checked`: the count is the number of files found, not the number
checked. Compute the list that is really passed (`paths` or the found files) and count that.

### 2.2 `release.publish` crashes with `EOFError` without a terminal — medium **[verified]**

`_confirm` calls `input()`. With no stdin (`< /dev/null`, a cron job, many CI runners that forget
`CI=true`) the task ends with an `EOFError` traceback after the checks and the build question.
Catch `EOFError` and `KeyboardInterrupt`, and exit with
`Publication not confirmed: pass --yes to publish without a terminal`. (This was checked by
calling `_confirm` directly; `release.publish` itself was deliberately not run.)

### 2.3 One token variable for PyPI and TestPyPI — medium **[reading]** **[breaking]**

`PYPI_TOKEN` is used for `--test-pypi` as well. A PyPI token is rejected by TestPyPI (and the
reverse), so the user has to change the variable between runs, and a production token is sent to
the test index if set. Read `TEST_PYPI_TOKEN` (fallback: none) when `test_pypi` is set, and say so
in the missing-credentials message.

### 2.4 Emojis become `?` on an ASCII terminal — low **[reading]**

`say` falls back to `encode(..., "replace")`, which gives `?  Running tests...`. It never fails
(good), but the output is hard to read. Map the few symbols used (`✅ ❌ ⏭️ 📦 ...`) to ASCII tags
(`[ok]`, `[fail]`, `[skip]`) in the fallback, and honour `NO_COLOR`/an
`INVOKE_TASKLIB_ASCII=1` switch. The symbols are a closed set, so a dict is enough.

### 2.5 `test.doctest-src` ignores `tasklib.test.xdoctest` — low **[reading]**

`doctest_src` hard-codes `pytest --xdoctest` while `_run_pytest` reads `test.xdoctest`. A project
that sets `xdoctest: false` (because the plugin is not installed) still gets
`unrecognized arguments` from `test.doctest-src`, and thus from `test.doctest` and the CI. Either
document that the key does not apply to it or, better, give it the plugin check of 1.3.

### 2.6 Relative import above the top-level package is silently accepted — low **[verified]**

`parse_imports("from ... import x", "pkg.a")` returns `[('', ('x',))]` instead of failing: the
`package[: len(package) - (level - 1)]` slice goes negative. The edge then resolves to nothing and
the import is ignored by `imports.check-cycles`. Raise a `SyntaxError`-like error (what Python does:
`attempted relative import beyond top-level package`) and report it as a parse failure.

### 2.7 `_Tarjan` uses `c in self.stack` on a list — low **[reading]**

`_advance` and `_pop_component` test membership and `index()` on a Python list, which is
O(stack depth) for each edge: quadratic on a large package. Keep an `on_stack: set[str]` next to
the list. Not urgent (the graphs are small), but trivial and it removes the only non-linear step.

### 2.8 `env.create-venv` installs an unpinned `invoke` — low **[reading]**

`uv pip install invoke` takes the latest `invoke`, ignoring the `invoke>=3.0,<4.0` bound of the
project and not installing `invoke-tasklib` itself, so the `tasks.py` of the project fails right
after (`ModuleNotFoundError: invoke_tasklib`). Either `uv sync` the groups after creating the
environment or install `invoke-tasklib` with the same bound.

### 2.9 `clean.all` removes `build` and `dist` without a way to preview — medium **[reading]**

`build/`, `dist/`, `site/` (if a mkdocs file exists) and `.benchmarks` are removed unconditionally.
A project that keeps scripts or assets in a tracked `build/` directory loses them with no
confirmation, and `shutil.rmtree` does not use the trash. Add `--dry-run` (print the `Removing`
lines only) and refuse to remove a directory that contains tracked files
(`git ls-files --error-unmatch`/`git check-ignore`), or at least a `tasklib.clean.extra`/`exclude`
config.

## 3. Design and API

### 3.1 There is a `check.all` but no `fix.all` — medium

The naming rule is `check_<target>` / `fix_<target>`, and `check.all` runs the checks, but fixing
needs four commands (`format.fix-python`, `format.fix-docstrings`, `lint.fix-python`,
`format.fix-shell`). Add `fix.all` with the same `tasklib.fix.tasks`, `--only`, `--skip` and
`--keep-going`, running the fixers in the order that converges (`lint.fix-python` before
`format.fix-python`). `check.py` and `fix.py` can share the step runner.

### 3.2 The module names do not match the namespaces — low **[breaking]**

`formatting` -> `format`, `typecheck` -> `types`, `testing` -> `test`. The docstring of
`__init__.py` has to explain the `Collection.from_module(testing, name="test")` workaround. Rename
the tasks by `@task(name=...)` or give each module a `NAMESPACE`/`ns` attribute so that
`Collection(lint, testing)` needs no special case, and let `make_ns` read it (it removes the
`_MODULES` dict and the risk of two lists getting out of sync).

### 3.3 Remove the deprecated `invoke_tasklib.ns` — low **[breaking]**

`__getattr__`, `_shared_ns` and `functools.cache` exist only for the deprecated attribute. The
version is `0.0.x`; set a removal date (next minor) in the changelog, and delete them with their
tests and the sentence in `troubleshooting.md`.

### 3.4 `config.py` is 1,062 lines and repeats itself — medium **[reading]**

- `_normalize_groups`, `_validate_cov_reports` and `_validate_check_tasks` each re-implement
  "comma-separated string or list of strings -> stripped, deduplicated tuple". Extract
  `_as_names(key_path, value) -> list[str]` once; the three validators keep only their own check
  (allowed values, non-empty).
- `_validate_int`, `_validate_str`, `_validate_bool` have the section hard-coded in the message
  (`tasklib.test.{key}` / `tasklib.{section}.{key}`) in an inconsistent way: `_validate_int` and
  `_validate_bool` cannot be used outside `test`. Pass the section like `_validate_str` does.
- `get_config` has a check `if not package["name"]` followed by `_validate_str(...)` which repeats
  it, and derives `import_name`, `src` and the test paths inline. Move the derivations into
  `_derive_defaults(merged)`.
- The dataclasses, `SCHEMA` and `_SECTION_CLASSES` must stay in sync by hand (a test checks it).
  Generate the JSON schema and the table of `uguide/config.md` from the dataclasses
  (`dataclasses.fields`) plus `Option.doc`, or drop the dataclasses for the section classes built
  from `SCHEMA`.
- Split into a package: `config/_schema.py` (Option, SCHEMA), `config/_validate.py`,
  `config/__init__.py` (`get_config`, `load_config`). Public imports do not change.

### 3.5 A `config.show` task — low

Users debug "which value was used" by reading the code. A read-only `config.show` task (or
`python -m invoke_tasklib.config --resolved`) printing the resolved config as YAML, with the
origin of each value (default, `invoke.yaml`, environment variable), would answer most of the
questions of `troubleshooting.md`. `main` of `config.py` already prints the JSON schema; publish
that file in the docs (`schema.json`) so editors can use it with `# yaml-language-server: $schema=`.

### 3.6 Progress output is not uniform — low **[reading]**

`step` gives the `❌ Failed: ...` line; `say` does not. `test.benchmark`, `test.doctest-markdown`,
`doc.serve`, `doc.publish-*`, `env.*`, `imports.*` and `release.*` use `say` with a start and a
done line, so when they fail there is no failure line. Use `step` everywhere a start/done pair
exists. For `doc.serve` (long-running), keep `say`.

### 3.7 `types.check --complete` drops `--args` for pyright — low

`args` is passed to `ty` only, and pyright cannot be given options at all. Add `--pyright-args`
(or accept `args` for both as `--args`/`--complete-args`). The `paths` default of `ty` is the
project; pyright uses its own `include`, so the two checks can look at different files. State
that in the help.

### 3.8 `python_version` default is a constant — low

`package.python_version` defaults to `"3.14"`, which will be wrong as soon as 3.15 is stable or if
the project's `requires-python` is lower. Derive the default from a `.python-version` file or the
lower bound of `requires-python` in `pyproject.toml` (already read by `release._project_version`).
In this repo the `.venv` is Python 3.12 while `invoke.yaml` says 3.14: nothing tells the user.
`env.install` could warn when `sys.version_info` differs.

### 3.9 Aliases in `tasks.py` — low

`tasks.py` adds `build-package` as an alias of `release.build`. If it is meant as the documented
example of extending a namespace, say so in `custom_tasks.md`; if it is a leftover (CI uses
`release.build`), remove it so that `inv --list` of the project is the one that users see.

## 4. Tests

Strengths: 100% line and branch coverage, a real integration suite (`mike`, git, quoting, the
runner with a stripped `PATH`), patched behaviour matched by integration tests. The deviations from
the project's own rules:

- **`pytest.raises` without `match`** (rule of `CLAUDE.md`) — **[verified]**: 12 occurrences,
  e.g. `tests/unit/test_imports.py:150`, `test_check.py:173`, `test_runner.py:133,238,324`,
  `test_doc.py:469`, `test_config.py:586,1094`, `test_output.py:125,149`,
  `test__discover.py:121`. A few check `info.value.code` afterwards; assert the message with
  `match=` too (for `Exit`, the message is exactly the user's explanation).
- **Logic in test bodies**: `for`/`if` in `tests/unit/test__discover.py:20`,
  `test_check.py:36`, `test_release.py:110`, `test_testing.py:28,34`. They are in helper
  functions building file trees; move them to fixtures or `parametrize` so a test body is flat.
- **More than one assert** in a test: `test_runner.py::test_python_executable_quotes_path_with_space`.
  The tuple comparison trick used in `test_config.py:1096` (`assert (a, b) == (...)`) is a way to
  have two behaviours in one assert; prefer two tests.
- **Add the tests for the items above**, each with its regression check (`git stash push src`):
  1.1 (unit + integration), 1.2 (the hint table covers every program), 1.3, 1.5 (a parametrize of
  the shell forms), 2.1, 2.2 (`monkeypatch.setattr("builtins.input", raise EOFError)`), 2.6.
- **Mutation or property testing** for `_graph.py` and `build_command`: the quoting round trip
  (`shlex.split(build_command(...))` equals the words in) is a good `hypothesis` property, and
  `find_cycles` can be checked against a brute-force reachability on random small graphs with a
  seeded generator. Both are cheap and the modules are the two with real algorithms.

## 5. Packaging, config and tooling

- **sdist** (`only-include = ["src"]`) **[reading, the sdist was not built]**: the sdist is
  limited to `src`, so it has no tests, so downstream packagers cannot run them. Include `tests`
  (and check that `README.md` and `LICENSE` are in it) or drop `only-include`.
- **Classifiers**: add `Typing :: Typed` (the package ships `py.typed`) and
  `Programming Language :: Python :: 3 :: Only`. The `License ::` classifier next to an SPDX
  `license = "BSD-3-Clause"` is deprecated by PEP 639; keep only the expression.
- **Dev dependencies**: `pygments` is listed but nothing in the repo uses it directly (pytest
  already depends on it); `feu[all]` is only used by `dev/generate_versions.py` and pulls many
  packages, so a `bot` group would keep the `dev` group light. `pytest-benchmark` is missing while
  `test.benchmark` needs it (see 1.3).
- **Line length of docstrings**: `max-doc-length = 72` is enforced by ruff (E W505) and
  docformatter, good; the `lint.ignore` has `E501`, so the 100-column code limit is enforced only
  by `ruff format`, which does not break long strings. **[verified]** 8 lines go over 100 columns:
  `src/invoke_tasklib/check.py:131` (107, the help of `only`) and 7 lines in
  `tests/unit/test_clean.py:144`, `test_config.py:713`, `test_imports.py:170` and
  `test_testing.py:47,95,106,138`. `CLAUDE.md` says ruff enforces the limit; it does not. Remove
  `E501` from the ignore list and fix these lines.
- **Windows**: the README says it is unsupported, but the classifiers and CI agree only by
  omission. Make the first run on Windows fail with an explicit message
  (`invoke-tasklib supports Linux and macOS only`) from `make_ns`, so the cause is not
  `'find' was not found on the PATH`. (The same style as 1.)
- **Pre-commit**: the `ty` hook runs `uv run inv types.check`, which is slow and not isolated;
  fine, but `pass_filenames: false` plus `types: [python]` runs on every commit that touches
  Python. Consider `stages: [pre-push]` for it and for any hook over 2 s.

## 6. CI

CI is in good shape: every action is pinned by SHA, `permissions: contents: read` is set on the
workflows, jobs call the project's own `inv` tasks (dogfooding), and coverage is uploaded from one
cell only. Remaining suggestions:

- `check.all` is not run in CI; the jobs call the tasks one by one. Adding one job with
  `inv check.all --keep-going --only doctest,spelling,docs,audit` (the steps that are not in the
  default list) would catch drift of the composite task itself.
- Add a job that runs the full test suite with a **stripped `PATH`** on Linux (`env -i`), to
  validate the missing-tool messages of section 1 on a system where `cd` is not an executable.
- `ci-test.yaml` uses `timeout-minutes: 5` while the integration suite takes 18 s locally; fine,
  but a `--durations` budget would warn when `mike` tests (1-2 s each, 7 of them) grow.

## 7. Suggested order of work (one PR each)

1. `check.all --keep-going` prints the reasons (1.1) + tests.
2. Hints: `git`, `uvx`, `pre-commit`, groups table, test that every program has a hint (1.2).
3. `check_program` false positives (1.5).
4. pytest plugin check (1.3) + `doctest_src` (2.5).
5. `env.check-tools` and the `check.all` pre-flight (1.6).
6. Small bugs: 2.1, 2.2, 2.6, 2.7, 2.8.
7. `release`: `TEST_PYPI_TOKEN` (2.3) **[breaking]**.
8. `clean --dry-run` (2.9).
9. Tests that break the rules of `CLAUDE.md` (section 4).
10. `fix.all` (3.1), then the structure changes (3.2, 3.3, 3.4) as a "0.1.0" release.
11. Packaging and CI items (sections 5 and 6).

## What was and was not done

- Done: the code was read, the baseline run, and 1.1, 1.2, 1.5, 2.1, 2.2 (via `_confirm` only), 2.6
  were reproduced with the real tools or a probe script kept outside the repository.
- Not done: no source file or test was changed; `release.publish` was not run (it publishes);
  CI results, the `docs/` pages other than the four named above, and `.make/` were not reviewed;
  the items marked **[reading]** were not run and may need a second look before a PR is written.
