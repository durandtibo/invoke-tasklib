# Review of `invoke-tasklib` — suggestions

This review replaces the previous one (#199). Nearly all of it has been done since (the `check.all`
`--keep-going` reasons, the hints and the pytest-plugin check, `env.check-tools`, the pre-flight,
`fix.all`, `clean --dry-run`, `TEST_PYPI_TOKEN`, `config.show`, the split of `config.py`, the
`match=` of `pytest.raises`, ...). The review was redone on the current code. The old text stays in
the git history.

## Scope and method

Read line by line:

- `src/invoke_tasklib/`: all 25 files (5,719 lines), including `config/` and `_steps.py`,
  `_graph.py`, `_discover.py`;
- `pyproject.toml`, `invoke.yaml`, `tasks.py`, `.pre-commit-config.yaml`, `CLAUDE.md`;
- `docs/docs/dev/architecture.md`, and the README / `docs/docs/index.md` / `uguide/index.md` task
  tables (checked against `inv --list`).

Checked with tools or scripts, not read:

- the test tree (`tests/`, 8,060 lines in `unit/` and `integration/`) with an `ast` script for the rules of
  `CLAUDE.md` (asserts per test, logic in tests);
- the CI workflows (30 files) by `grep` for the `inv` tasks they run. The workflows were **not** read
  in full.

Not reviewed: `.make/` (vendored), `docs/docs/uguide/*` and `docs/docs/refs/*` other than by the
checks above, the content of the 1,759 tests beyond the sample the scripts hit.

Baseline on `main` (`2efea1c`, only this file changed): `pytest tests` 1759 passed in 19 s;
`ruff check` and `ty check` clean. The doctests and CI were not re-run.

Legend: **[verified]** reproduced here with the real tools or a probe script (the scripts were kept
outside the repository); **[reading]** found by reading, not run. Severity: high / medium / low.
**[breaking]** changes a public behaviour or signature (allowed by the request).

## Summary: what to do first

1. `release.publish` skips its confirmation when `CI=false` or `CI=0` (1.1). A one-line fix, and it
   guards an irreversible action.
2. `doc.publish-latest` picks the wrong default version when a release candidate was tagged (1.2).
3. `clean.all` does not remove `docs/site`, the default output of the default `docs_config` (1.3).
4. The ASCII output mode deletes accented characters of paths and messages (1.4).
5. Then the design items of section 2: one registry for the steps and their tools (2.1), the
   layering leaks (2.2), the module names (2.3), keyword-only options (2.5).

## 1. Bugs and defects

### 1.1 `CI=false` (or `CI=0`) turns the publish confirmation off — high **[verified]**

`release.publish` tests `os.environ.get("CI")`, which is truthy for any non-empty string:

```text
$ CI=false python -c 'import os; print(bool(os.environ.get("CI")))'
True
```

So `CI=false inv release.publish` (or a shell that exports `CI=0`) publishes to PyPI without asking,
and the help says "never asked when the CI variable is set". `publish` cannot be undone, which is
why the confirmation exists.

Suggestion: add `_in_ci()` to `release.py` (or `runner.py`) that is true when `CI` is set to
something other than `""`, `0` and `false` (case-insensitive), and use it there. The same helper
serves any later task that behaves differently in CI. Tests: a parametrize over `""`, `"0"`,
`"false"`, `"FALSE"` (a confirmation is asked) and `"1"`, `"true"` (not asked).

### 1.2 `doc.publish-latest` skips the final release after a release candidate — medium **[verified]**

`_last_version_tag` relies on `git tag --sort=-v:refname`. Git's version sort puts a suffix after the
bare version, so `v1.2.0rc1` sorts **before** `v1.2.0` in the descending list:

```text
$ git tag --list 'v[0-9]*' --sort=-v:refname      # tags: v1.2.0, v1.2.0rc1, v1.1.0
v1.2.0rc1
v1.2.0
v1.1.0
```

With no `--version`, `publish_latest` takes `v1.2.0rc1`, sees a pre-release, prints
`Skipping the pre-release version` and publishes nothing, although `v1.2.0` exists and is the tag
being released. `test_last_version_tag_sorts_by_version` only covers plain tags (and has a loop, see
4.2).

Suggestion: list the tags without the sort option, parse each with `_parse_release`, drop the
pre-releases and take the maximum on `(major, minor, patch)`. That also removes the dependency on
the user's `versionsort.suffix` git config. Regression test: a real repo (integration) with the three
tags above; the expected tag is `v1.2.0`.

### 1.3 `clean.all` leaves `docs/site` — medium **[verified]**

The default `paths.docs_config` is `docs/mkdocs.yml`. MkDocs resolves `site_dir` relative to the
config file, so the build goes to `docs/site`:

```text
$ mkdocs build --config-file docs/mkdocs.yml   # in a project with docs/mkdocs.yml
$ ls -d site docs/site
ls: site: No such file or directory
docs/site
```

`clean.all` removes `SITE_DIR = "site"` (and only when a config file exists). With the default
layout it never removes the output of `doc.build`. The repo's own `.gitignore` has `/site`, anchored
at the root, so the same layout also shows `docs/site` as untracked in `git status`.

Suggestion: remove `<dirname of paths.docs_config>/site` (via `load_config`), and, better, read
`site_dir` from the mkdocs file when it is set (a three-line `yaml.safe_load` would add a dependency;
a regex on `^site_dir:` is enough for the plain case). Add `docs/site` to the `.gitignore` of this
repo. `clean.all` then needs the config, which it does not load today; keep it working without
`package.name` (catch the `Exit` and fall back to `site`) so the task still runs on a bare checkout.

### 1.4 `INVOKE_TASKLIB_ASCII=1` deletes accented characters — low **[verified]**

`_NON_ASCII` matches every non-ASCII character, not only the emojis:

```text
>>> _to_encoding("✅ Removing café/é.py\n", "ascii")
'[ok] Removing caf/.py\n'  # codespell:ignore caf
```

A path or a message with an accent is silently changed, so the output names a file that does not
exist. The same fallback runs when a stream cannot encode a character (`LANG=C`), and then
`encode(..., "replace")` is never reached for these characters, so even `?` is lost.

Suggestion: restrict the removal to the emoji ranges (`U+1F000–U+1FAFF`, `U+2600–U+27BF`,
`U+2B00–U+2BFF`, `U+FE0F`) and let the final `encode("replace")` (or `backslashreplace`) handle the
rest. Add a test with `"café"` in both modes.

### 1.5 `check_program` still rejects some valid shell — low **[verified]**

The previous false positives (`FOO=1 cmd`, `(ls)`, `$(...)`, `cd`) are fixed. Three remain:

- shell keywords and `!`: `if true; then ls; fi`, `for f in a; do ls; done` and `! grep x f` report
  `'if' was not found on the PATH`;
- `~/bin/tool` is reported as not found: `shutil.which` does not expand `~`, the shell does;
- wrappers (`time`, `sudo`, `nice`, `env VAR=1 cmd`) only check the wrapper, not the program they
  run, so `sudo ruff` passes when `ruff` is missing. This is a missed message, not a wrong one.

`run(..., check=False)` exists and is the answer for a real custom task, so this is low. Cheap
improvement: skip a stage whose first word is a shell keyword (`if`, `for`, `while`, `case`, `!`,
`then`, `do`) or contains a `/`, and extend the `xargs` branch of `_program_of` to `env`, `sudo`,
`time`, `nice`. Alternatively, drop `xargs` support entirely (see 2.4: it only exists because of the
`find | xargs` pipeline).

### 1.6 `build_command` makes globs and `~` literal — low **[verified]**

```text
>>> build_command("ruff", args="--x '$HOME' *.py", paths="a\\ b")
"ruff --x '$HOME' '*.py' 'a b'"
>>> build_command("ruff", paths="~/x")
"ruff '~/x'"
```

The quoting is the point of the function (and is tested), but it means `--paths "src/*.py"` reaches
the tool as the literal `src/*.py`. `ruff` expands a glob by itself; `codespell`, `shellcheck` and
`docformatter` do not, and `~` is never expanded. Say it in `PATHS_HELP` ("globs and `~` are passed
as they are") or expand with `glob.glob` / `Path.expanduser` before quoting. Documenting is enough.

### 1.7 `check.all` cannot enforce `cov_fail_under` — medium **[reading]**

The `unit` step calls `testing.unit(c)` with `cov=False`, and `cov_fail_under` is only passed with
`--cov`. A project with `test.cov_fail_under: 100` (this repo) gets the threshold from `inv
test.all --cov` in CI and never from `check.all`. Two ways: a `tasklib.check.cov` boolean, or a
`unit-cov` step in `CHECK_STEPS`. The first is smaller.

### 1.8 `release.publish --test-pypi` falls back to `UV_PUBLISH_TOKEN` — low **[reading]**

The docstring says `TEST_PYPI_TOKEN` is read with `--test-pypi` "so a PyPI token is never sent to
TestPyPI", but `token = environ.get(token_name) or environ.get("UV_PUBLISH_TOKEN")` applies the
fallback to both targets. `UV_PUBLISH_TOKEN` is usually the production token. Either drop the
fallback for `--test-pypi` or reword the docstring. The first is safer and matches the sentence.

### 1.9 `release.build` assumes a wheel **and** an sdist in `dist/` — low **[reading]**

The verification loop requires `*.whl` and `*.tar.gz`. `inv release.build --args "--wheel"` builds
and then fails with `No file matching '*.tar.gz' found in 'dist'`, and `--args "--out-dir out"`
verifies a stale `dist/`. Verify the files that the build produced (compare `dist/` before and
after, or parse the `Successfully built` lines of `uv build`), and skip a kind that was not asked
for.

### 1.10 Minor

- `testing.coverage_report` prints `htmlcov/` and opens `htmlcov/index.html`: a
  `[tool.coverage.html] directory` in the project is ignored **[reading]**.
- `env.create-venv` runs `uv venv --clear` with no confirmation or `--dry-run`, and the invoke that
  runs it often lives in that very `.venv`. The docstring warns, but this is the only destructive
  task without a guard (`clean` and `publish` have one) **[reading]**.
- `test.all` has no `skip_missing`, unlike `unit`, `integration` and `functional`: with no `tests/`
  directory it fails with pytest's own message instead of the `⏭️ No 'tests' directory` line
  **[reading]**.

## 2. Design

### 2.1 Five lists describe the same steps and tools — medium **[reading]**

Adding a step to `check.all` means editing, in four files:

| What                               | Where                                           |
| ---------------------------------- | ----------------------------------------------- |
| the name                           | `CHECK_STEPS` (`config/_constants.py`)          |
| the default selection              | a comma-separated string in `config/_schema.py` |
| the task                           | `check.STEPS`                                   |
| the programs and the modules       | `check.PROGRAMS`, `check.MODULES`               |
| the tool list of `env.check-tools` | `env.TOOL_PROGRAMS`, `env.TOOL_MODULES`         |
| the install hint                   | `runner.PROGRAM_HINTS`, `PROGRAM_GROUPS`        |

`fix.py` repeats the pattern (`FIX_STEPS`, `STEPS`, `PROGRAMS`). The `types` step is checked for
`ty` only, but `types.check --complete` also needs `pyright`; `unit` has an `if step == "unit"` in
`_missing_tools` for `xdoctest`. The lists are kept in line by tests (I did not find a test that a
program of `PROGRAMS` is in `TOOL_PROGRAMS`; add it if it does not exist).

Suggestion: one registry in `_steps.py`:

```python
class Step(NamedTuple):
    task: Task
    programs: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()  # or a callable(cfg) for xdoctest
```

`check.STEPS` and `fix.STEPS` become `dict[str, Step]`; `CHECK_STEPS` is a literal tuple of names
kept in `_constants` (config must not import the task modules) with one test that its names equal
`check.STEPS`; `env.TOOL_PROGRAMS` is the union of the programs of both registries plus the system
tools; the test of "every program built by a task has a hint" (4.3) then runs over the registry.

### 2.2 Layering leaks — low **[verified by grep]**

- `_steps.py` imports `find_tool` from `env.py` (a task module), and `testing.py` imports the
  private `_split` from `runner.py`. Move `find_tool` to `runner.py`, rename `_split` to a public
  `split_args` (it is already the documented behaviour of `build_command`).
- The "X was not found" message is written in three places with three wordings:
  `runner.check_program` (`'x' was not found on the PATH. <hint>`), `_steps.missing_tools` (same, plus
  a module variant) and `env.check_tools` (`❌ x: program not found. <hint>`). A single
  `runner.not_found_message(name, module=False)` makes them agree, and a change of hint wording
  becomes a one-line change.
- `config/__init__.py` holds `get_config` and `load_config` and re-exports six private names
  (`_derive_defaults`, `_as_mapping`, `_check_keys`, `_validate_str`, `_defaults`, `_SECTION_CLASSES`)
  only to call them. Move the two functions to `config/_resolve.py` and keep `__init__` as the
  public re-exports; the `Raises:` paragraph of `get_config` (a 20-line list of every rule) can
  become a pointer to `uguide/config.md`, which is the place that lists the rules.

### 2.3 Module names, namespace names and `configuration` — low **[breaking]**

The previous review's item 3.2 is still open: `formatting`/`typecheck`/`testing` are exposed as
`format`/`types`/`test`, through a `_MODULES` dict and, for a hand-made collection, the workaround
in the docstring of `__init__.py` (`Collection.from_module(testing, name="test")`). The module
`configuration.py` (task `config.show`) now sits next to the package `config/` and the namespace
`config`, three things with nearly the same name.

Suggestion: a `NAMESPACE = "test"` constant in each task module, read by `make_ns` and documented
for `Collection.from_module(module, name=module.NAMESPACE)`, so the `_MODULES` dict and the docstring
workaround go. Rename `configuration.py` to `config_tasks.py`... or to `show.py`; any name that does
not collide. This is a rename of public modules, so do it in the same release as 2.4.

### 2.4 Replace `find | xargs` by a Python file walk — low **[reading]**

`format.check-shell` and `fix-shell` build `find . \( -name .git -o ... \) -prune -o -name '*.sh'
-print0 | xargs -0 -r <tool> --`. `testing` (markdown) and `clean` (pycache) already walk the tree
with `os.walk`. The result is two mechanisms and three excluded-directory sets
(`EXCLUDED_DIRS`, `SHELL_EXCLUDED_DIRS`, `MARKDOWN_EXCLUDED_DIRS`) plus the `clean.DIRS`.

A single `find_files(root, suffix, excluded)` in a small `_files.py`:

- is testable with `tmp_path`, without a shell, and does not depend on `xargs -r` (GNU/BSD
  differences) or on `find` flavours;
- passes the files as arguments, so `xargs` support in `_program_of` and its tests can go (see 1.5);
- gives one place for "which directories does a task never enter".

Cost: a very long argument list on a huge repo (the same limit `xargs` handles by batching); fine for
shell scripts.

### 2.5 Options should be keyword-only everywhere — low **[breaking for Python callers]**

`CLAUDE.md` asks for keyword-only options. 27 of the 40 tasks still have positional-or-keyword
options (`args`, `paths`, `cov`, `push`, `version`, ...); the other 13 have `*` or no option. `inv`
accepts both (the command line only uses flags, and `check_cycles` already shows it works). Add `*`
after `c` in those 27 tasks; the only effect is on Python callers like `doctest_src(c)`, which pass nothing.
`types.check` mixes both (`complete, args, paths, *, pyright_args`).

### 2.6 Progress output is still not uniform — low **[reading]**

Open since the previous review: only the tasks that use `step()` print `❌ Failed: ...`. These use
`say` for a start and a done line and so print no failure line: `test.doctest-markdown`,
`test.benchmark`, `doc.publish-dev`, `doc.publish-latest`, `env.install`, `env.update`,
`env.create-venv`, `imports.check-isolated`, `release.build`, `release.publish`. `doc.serve` should
keep `say` (long-running).

While in there, `step` could print the duration (`✅ Linting check passed (1.2 s)`) and `run_steps`
could end with one line per step (name, status, duration). Both are cheap and help to see which step
of `check.all` is slow. Optional.

### 2.7 Tools run through `uvx` are not pinned — low **[reading]**

`security.audit` runs `uvx pip-audit` and `release.build --check` runs `uvx twine check`: the latest
release from PyPI on each run, with the developer's environment and, in CI, with the job's token
variables around. The tools are not in a lock file, so the result is not reproducible and a
compromised release of either is run on the next invocation. Pin a range as a constant
(`uvx --from 'pip-audit>=2.10,<3'`) or run them with `uv run --with`. This repo already has
`pip-audit` in its `dev` group, so `uv run pip-audit` would use the lock file for the project itself.

### 2.8 `imports.check-isolated` starts one process and prints one command per module — low **[reading]**

For a package of 300 modules the task echoes 300 `python -c 'import x'` lines and starts 300
interpreters one after the other. One worker (`python -m invoke_tasklib._discover --import-each`)
that imports each module in a fresh subprocess, optionally in parallel, and prints one summary line
and the list of failures would be as strict and far quieter. It is also not a `check.all` step.

### 2.9 `config.show` depends on private attributes of Invoke — low **[reading]**

`LEVELS` reads `config._defaults`, `_collection`, `_system`, `_user`, `_project`, `_env`, `_runtime`,
`_overrides` and `_modifications`, and `getattr(..., None)` hides a rename: the origin silently
becomes `derived`. `invoke>=3.0,<4.0` allows any 3.x. The `test-deps` CI job runs only the unit
tests, so make sure `test_configuration` (the unit test of `_origin` with a real `Config`) is in it,
and add one test that every attribute of `LEVELS` exists on a fresh `Config()`, so an Invoke change
fails loudly.

### 2.10 `pytest-timeout` is a hard requirement — low **[reading]**

`_run_pytest` always adds `--timeout`, and `check.MODULES["unit"]` lists `pytest_timeout`. A project
that does not want the plugin must still install it. Offer `tasklib.test.timeout: false` (or skip
`--timeout` when the plugin is absent, with a `⏭️` line), like `xdoctest` is optional.

### 2.11 Remove the deprecated `invoke_tasklib.ns` — low **[breaking]**

Open since the previous review. `__getattr__`, `_shared_ns` and `functools.cache` exist only for it.
The project is at `0.0.8`; announce the removal in the release notes and delete it with its tests,
the `Note` in the docstring of `__init__.py` and the paragraph in `architecture.md`.

## 3. Documentation

- **`architecture.md` is out of date [verified]**: it lists `DEFAULT_PACKAGE` ... `DEFAULT_CHECK` but
  not `DEFAULT_FIX`; its `TasklibConfig` snippet has no `fix` field; its list of task modules stops at
  `check.py` (no `fix.py`, no `configuration.py`); "Three small modules support the task modules"
  lists `runner`, `output` and `_discover` but not `_steps.py` (the step runner shared by `check.all`
  and `fix.all`) or `_graph.py`.
- **`CLAUDE.md` has the same gaps [verified]**: its source layout omits `fix.py`, `configuration.py`,
  `_steps.py`, `_graph.py` and `_discover.py`. An agent that follows it will not know that
  `check.py` and `fix.py` share `_steps.py`.
- The README task table, `docs/docs/index.md` and `uguide/index.md` do list every task of
  `inv --list` (checked by script), and `docs/docs/schema.json` equals the output of
  `python -m invoke_tasklib.config`. Both are guarded by tests today; keep them.
- Add one page, "Adding a step to `check.all`" (or a section of `architecture.md`), once 2.1 is done:
  with five places to edit the process is easy to get wrong.

## 4. Tests

Strengths: 1,759 tests, 100% line and branch coverage, a real integration suite (mkdocs/mike, git,
quoting, a stripped `PATH`), and the `match=` rule is now applied everywhere (the 12 occurrences of
the previous review are fixed).

### 4.1 One `raises` plus an assert in the same test — low **[verified]**

`CLAUDE.md`: "a test has one `assert` or one `pytest.raises`". 61 tests have both, nearly all the
same shape:

```python
with pytest.raises(Exit, match="...") as info:
    task(c)
assert info.value.code == 127
```

for example `test_env.py::test_check_tools_missing_tool_exits_with_code_127`,
`test_runner.py::test_check_program_missing_program_exit_code`, `test_check.py::
test_all_keep_going_exits_with_code_1`, `test_output.py::test_step_raises_the_same_exception`,
`test_release.py::test_publish_asks_for_a_confirmation`. Two clean options: a helper in
`tests/helpers.py`, `exit_code(fn, *args) -> int`, that wraps the `raises` and returns
`info.value.code`, so the test is a single `assert exit_code(...) == 127` (and a second test checks
the message with `match=`); or make the rule explicit in `CLAUDE.md` (one `raises` may be followed by
assertions on the caught exception). The second is a one-line change and honest about what the suite
does; the first is stricter. Pick one, because today the rule and the suite disagree.

### 4.2 Logic in a test body — low **[verified]**

One test has a loop: `tests/integration/test_doc.py::test_last_version_tag_sorts_by_version`. The AST
scan found no other test with `for`/`while`/`if`, and no test with two `assert`s. Parametrize it
(it will need new cases for 1.2 anyway).

### 4.3 Missing tests — medium

- 1.1 to 1.4, each with its regression check (`git stash push src`): `CI` values, the rc tag
  (integration, real git), `docs/site` (unit with the `MockContext` + `tmp_path`), the accent.
- "Every program that a task builds has an install hint": collect the first word of every command
  recorded by `MockContext` over all the tasks (the `check`/`fix` registries give most of them) and
  assert it is in `PROGRAM_HINTS`, `PROGRAM_GROUPS` or `UNCHECKED_PROGRAMS`. The previous review asked
  for it; `grep` finds no such test. A new tool then cannot be added without a hint.
- The contract tests of 2.9 (`LEVELS` attributes exist on `Config`).
- Property tests for the two modules with real algorithms: `shlex.split(build_command(...))`
  round-trips the words, and `find_cycles` agrees with a brute-force reachability on random small
  graphs from a seeded generator (`default_rng(0)`). Both are cheap. Still absent.

### 4.4 Lines over 100 columns — low **[verified]**

`pyproject.toml` ignores `E501`, so only `ruff format` enforces the 100 columns, and it does not
break strings or comments. `CLAUDE.md` says ruff enforces the limit. 14 lines are longer:

```text
src/invoke_tasklib/check.py:107 (107)     src/invoke_tasklib/fix.py:40 (103)
src/invoke_tasklib/runner.py:71 (106)     src/invoke_tasklib/typecheck.py:21 (102)
src/invoke_tasklib/config/_schema.py:200 (108)
tests/unit/test_check.py:351 (102)        tests/unit/test_clean.py:155, 441 (101)
tests/unit/test_imports.py:170 (102)      tests/unit/test_testing.py:50 (113), 98 (119), 109 (106), 163 (102)
tests/unit/config/test__validate.py:266 (101)
```

Fix the lines and remove `E501` from `lint.ignore`.

## 5. Packaging, config, CI

- **sdist [reading]**: `only-include = ["src"]` leaves out the tests, so downstream
  packagers cannot run them (check also that `README.md` and `LICENSE` are in it). Include `tests` and check the sdist contents
  (`tar tzf dist/*.tar.gz`); I did not build it.
- **Classifiers [verified]**: `Typing :: Typed` is missing (the package ships `py.typed`);
  `License :: OSI Approved :: BSD License` next to the SPDX `license = "BSD-3-Clause"` is deprecated
  by PEP 639 (keep the expression only).
- **`pytest-benchmark` [verified]**: `test.benchmark` needs it (`PLUGIN_OPTIONS` knows it) and the
  `dev` group does not list it, so `inv test.benchmark` on a fresh checkout stops with the plugin
  message. `nightly` runs `ci-benchmark.yaml`, so check how it installs it.
- **Windows [reading]**: the README says unsupported; `grep platform|win32 src` finds nothing. On
  Windows the first failure is `'find' was not found on the PATH`. If 2.4 is done the only blocker
  left is the `uv`/shell quoting; a one-line `make_ns` warning on `sys.platform == "win32"` would name
  the cause.
- **CI runs which tasks [verified by grep]**: none of `format.check-docstrings`, `format.check-shell`,
  `lint.check-spelling` (the pre-commit job covers `docformatter`, `shellcheck` and `codespell` with
  their own pins), `imports.check-isolated`, `security.audit` and `check.all` is run by an `inv`
  command in the workflows. `security.audit` is the one with no equivalent: the dependency-review
  workflow checks pull-request diffs, not the locked tree. A nightly `inv security.audit` and a
  `inv check.all --keep-going --only doctest,shell,spelling,docs,audit` job would exercise the tasks
  the repo ships to others but does not run itself. (The docs build is covered: `ci-doctest.yaml`.)
- The `ty` pre-commit hook runs `uv run inv types.check` on every Python commit; move it to
  `stages: [pre-push]` if it passes 2 s.

## 6. Suggested order of work (one PR each)

1. `CI` parsing in `release.publish` (1.1) + tests.
2. `_last_version_tag` (1.2) + a real-git integration test.
3. `clean.all` and `docs/site` (1.3), `.gitignore`.
4. ASCII mode and accents (1.4).
5. `check.all` coverage option (1.7), then the small items of 1.5, 1.6, 1.8, 1.9, 1.10.
6. Lines over 100 and `E501` (4.4); docs: `architecture.md`, `CLAUDE.md` (section 3).
7. The test-rule decision (4.1), then the missing tests (4.2, 4.3).
8. Layering (2.2), then the step registry (2.1) and the file walk (2.4).
9. Keyword-only options (2.5) and uniform output (2.6).
10. As one `0.1.0` release: module names (2.3), removal of `ns` (2.11).
11. Packaging and CI (section 5).

## What was and was not done

- Done: all of `src/` was read; the baseline ran; 1.1, 1.2, 1.3, 1.4, 1.5 and 1.6 were reproduced
  with the real tools (`git`, `mkdocs`, `python`) or a probe script outside the repository; the
  tests were scanned with `ast`; the task signatures were listed from a real `make_ns()`.
- Not done: no source file or test was changed. Items marked **[reading]** were not run and need a
  second look before a PR. `release.publish` was not run. The sdist was not built. The workflows were
  searched, not read, and CI results were not looked at.
