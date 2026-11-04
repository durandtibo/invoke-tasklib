# Review of `invoke-tasklib` — suggestions

This review replaces the previous one (#271). The code was read again from the start, and the old
text stays in the git history. Nearly everything in the old review has been done (see "What
happened to the previous review"), so this one is about what is left and about what the fixes
uncovered. Examples in this file are written as `text` blocks without the doctest prompt, on
purpose (see 3.1).

## Scope and method

Read line by line:

- `src/invoke_tasklib/`: all the modules (about 6,600 lines), including `config/`, `_steps.py`,
  `_graph.py`, `_discover.py`, `_files.py`, `tools.py` and `runner.py`;
- `pyproject.toml`, `invoke.yaml`, `tasks.py`, `CLAUDE.md`, `tests/helpers.py`.

Checked with tools or scripts, not read in full:

- the test tree (`tests/`, 1,347 test functions): an `ast` script for the rules of `CLAUDE.md`
  (asserts and `raises` per test, `match=`, loops, local imports), plus `grep`;
- the workflows: `grep` for the `inv` tasks they run and for the `docs-deps` input of the setup
  action. They were **not** read in full.

Not reviewed: `.make/` (vendored), the pages of `docs/docs/uguide/` and `docs/docs/refs/`, `dev/`,
and the content of most of the 2,702 tests.

Baseline on `main` (`c6b962f`): `pytest tests` 2702 passed, 13 skipped in 15 s; coverage 100%
(lines and branches, `TOTAL 1526 0 392 0`); `ruff check`, `ruff format --check` and `ty check`
clean. **`inv test.doctest` fails** (5 failures, all in `review/suggestions.md`, see 3.1). CI was
not looked at.

Legend: **[verified]** reproduced with the real tools or a probe project (kept outside the
repository); **[reading]** found by reading, not run. Severity: high / medium / low.
**[breaking]** changes a public behaviour or signature (allowed by the request).

## Summary: what to do first

1. `inv test.doctest` is red on `main`: the markdown doctest runs the `>>>` examples of the old
   review (3.1). This review has none, so merging it fixes it; the rule should be written down.
2. `env.install`, `env.create-venv` and `env.update` fail in a project without a `uv.lock`, because
   of `uv sync --locked` (1.1).
3. The tools that live in the virtual environment (`ruff`, `ty`, `mkdocs`, ...) are not found unless
   the environment is activated, although the Python modules are found, and the hint is wrong
   (1.2).
4. `release.build` imports the package from the current directory, so for a flat layout it can
   verify the source tree instead of the built artifact (1.3).
5. `release.publish --test-pypi` can send a PyPI token that is in the environment (1.4).
6. The docs integration tests (`mike`) never run in CI (3.2), and the benchmark job still measures
   nothing (3.3).

## What happened to the previous review

Done and verified on the current code: boolean and integer environment variables (`_validate_bool`,
`_validate_int`, `default_config` registers `None`), `clean` stays inside the project
(`_is_inside_project`) and cleans the configured HTML directory, the `tasklib` working-directory
guard (`_check_project_root`), the nested failure line (`_install`), the `--cov-report` syntax
(`term-missing:skip-covered`, `html:dir`), the `-backport` pre-release regex, `--all-extras` in the
audit, `--append` for `integration` and `functional`, `run_step` and its `STEP_ERRORS`,
`runner.capture`, `check_program` (first word only, the shell parser is gone), `Step.modules` as a
function of the config, the split `runner.py` / `tools.py`, `in_ci` / `in_github_actions`,
`package.python_version` optional (uv chooses), `project_files` (files listed by git),
`imports.check-isolated` summary, `CLAUDE.md` and `architecture.md`, the amended rule of `raises`
plus one `assert` (#288), the three `match=` and the loop of the previous list.

Still open from before: the namespace and module names (2.3), `imports.check-isolated` starts one
interpreter per module (2.5), the benchmarks (3.3), the `check.all` job for pull requests (3.3),
the property tests (3.4), `feu[all]` in the `dev` group (4).

## 1. Bugs and defects

### 1.1 `uv sync --locked` fails without a `uv.lock` — medium **[verified]**

`env._install` always runs `uv sync --locked`. A project that does not commit its lock file (common
for libraries) cannot use `env.install`, `env.create-venv` or `env.update`:

```text
$ cd probe && uv sync --locked          # a project with a pyproject.toml and no uv.lock
error: Unable to find lockfile at `uv.lock`, but `--locked` was provided. To create a lockfile,
run `uv lock` or `uv sync` without the flag.
```

`env.update` is saved by its first command (`uv lock --upgrade` creates the file), but the two
others are not, and the README promises the tasks for any project with a `pyproject.toml`.
`security.audit` has the same requirement (`uv export --locked`), which is fine for an audit but
should be said in its page.

Suggestion: pass `--locked` only if `Path("uv.lock").is_file()`, and say in the first line of the
task which mode is used (`📦 Installing from uv.lock...` / `📦 No uv.lock: resolving...`). Or add a
`tasklib.env.locked` option (`auto` by default). Test: both commands in the list of commands, and
one integration test with a real `uv` on a probe project.

### 1.2 Programs of the virtual environment are not found unless it is activated — medium **[verified]**

The tasks run the Python modules with `sys.executable` (`python -m pytest`, `-m coverage`), so they
work from `.venv/bin/inv` without an activated environment. The programs (`ruff`, `ty`, `pyright`,
`docformatter`, `codespell`, `pre-commit`, `mkdocs`, `mike`) are looked up on the `PATH`:

```text
$ env PATH=/usr/bin:/bin:<uv dir> .venv/bin/inv format.check-python
🎨 Checking code format with ruff...
❌ Failed: Checking code format with ruff
'ruff' was not found on the PATH. Install it with the 'dev' group: `uv sync --group dev`.
```

`ruff` is installed, in the same `bin` directory as the running interpreter. The two rules disagree
(a module is found, a program of the same environment is not), the hint tells the user to install
what is installed, and `CLAUDE.md` itself asks agents to call `.venv/bin/...` directly, where this is
the normal case. `uv run inv ...` (what the CI does) hides it.

Suggestion: add `Path(sys.executable).parent` to the front of the `PATH` used by the lookups
(`shutil.which(name, path=...)` in `find_tool` and `check_program`) and by the commands
(`env={"PATH": ...}` in `runner.run`, so `ruff` is also the one of the environment, not another one
that is earlier on the `PATH`). Change `not_found_message` to say where it looked. Tests: a fake
`bin` directory next to a patched `sys.executable`, and one integration test with the real `inv`
and a stripped `PATH` (the suite already has one for `check_program`).

### 1.3 `release.build` can verify the source tree instead of the artifact — medium **[verified]**

The check runs `uv run --isolated --no-project --with <artifact> -- python -c "import <name>"` from
the project root. `python -c` puts the current directory first on `sys.path`, so with a flat layout
(`<name>/` at the root, which `paths.src` supports) the import succeeds even if the artifact does
not contain the package:

```text
$ cd dir_with_foo_package && python -c "import foo" && echo ok
ok
$ python -I -c "import foo"
ModuleNotFoundError: No module named 'foo'
```

The task then reports `✅` for a wheel that is empty (a wrong `packages` setting in the build
backend is the usual cause, and it is the very mistake this check exists for). The same applies to
`imports.check-isolated` (`python -c "import <module>"`), which wants the installed package.

Suggestion: use `python -I -c ...` in `release.build`. In `check-isolated`, decide first which
package is checked (the installed one, or the one of the source tree) and say it in the docstring;
`-I` fits the first, `PYTHONPATH` of the source directory the second. Tests: the command list, and
an integration test that builds a flat-layout probe project whose `packages` is wrong and expects
the task to fail.

### 1.4 `publish --test-pypi` can send an inherited PyPI token — medium **[reading]**

The docstring says that `PYPI_TOKEN` is never sent to TestPyPI. The token is chosen correctly, but
it is given to `uv publish` with `env={"UV_PUBLISH_TOKEN": token} if token else {}`. Invoke merges
`env` into `os.environ` (`replace_env` is false), so with `--test-pypi`, no `TEST_PYPI_TOKEN`, and
Trusted Publishing in GitHub Actions, a `UV_PUBLISH_TOKEN` that the job defines for the real
publication is inherited by the child and read by `uv publish`, which then uploads it to
`test.pypi.org`. It needs a job that defines the variable and runs both targets, which is
plausible in a release workflow.

Suggestion: run `uv publish` with an environment built from `os.environ` without `UV_PUBLISH_TOKEN`
and `UV_PUBLISH_USERNAME`/`PASSWORD`, plus the chosen token (`replace_env=True`). Test: a patched
`os.environ` with the variable set, `--test-pypi` and no test token; assert the `env` passed to
`c.run`. Check with a real `uv publish --dry-run` that the inherited variable is read, before
fixing.

### 1.5 `html:<dir>` moves the report but not `coverage-report` and `clean` — low **[reading]**

`cov_reports` now accepts `html:cov_html` (the fix of the previous 1.5), and `pytest-cov` writes
the report there. `test.coverage-report` runs `coverage html` and `clean` removes a directory, both
from `_coverage_html_dir()`, which reads `[tool.coverage.html] directory` only. With the value in
`invoke.yaml`, `coverage-report` writes and opens `htmlcov/`, and `clean` leaves `cov_html/`. The
same goes for `xml:<path>` (`clean` removes `coverage.xml` only, never the moved file).

Suggestion: one helper `coverage_outputs(cfg)` in `testing.py` that returns the HTML directory and
the XML/JSON/LCOV paths from `cov_reports`, falling back to `pyproject.toml`, then to the defaults.
`coverage_report` passes `-d <dir>` to `coverage html`, `clean` removes what the helper lists (the
`keep_tracked` and inside-the-project rules stay). Test the three sources and their priority.

### 1.6 `check.all` never checks the format of the shell scripts — low **[reading]**

`format.check-shell` runs `shellcheck` only and `format.fix-shell` runs `shfmt -l -w`. So the `shell`
step of `fix.all` can rewrite files that the `shell` step of `check.all` accepted, which breaks the
rule of `CLAUDE.md` that `check_<target>` and `fix_<target>` are a pair. Suggestion: add
`format.check-shell-format` (`shfmt -d`, which exits non-zero on a diff) or give `check-shell` an
`--format` flag, and make the `check` step run both. Document the programs in `env.TOOL_PROGRAMS`
(`shfmt` is already there).

### 1.7 Minor

- **File selection differs between the two modes [reading].** In a git work tree, `project_files`
  ignores the `excluded` argument (it only filters `EXCLUDED_DIRS`), so `SHELL_EXCLUDED_DIRS` and
  `MARKDOWN_EXCLUDED_DIRS` apply outside git only. A tracked `build/run.sh` or `site/index.md` is
  checked in a repository and skipped in an export of it. This is the intended `.gitignore` policy,
  but the two constants and their docstrings still say "never checked". Say it, or drop the
  constants and keep `EXCLUDED_DIRS` for the walk.
- **`clean` removes a tracked `coverage.xml` [reading].** The directories use `keep_tracked`; the
  files of `FILES` do not. A project that commits `coverage.xml` or `.coverage` (rare, but the
  `FILES` list is fixed) loses it. Apply the same test in `_remove_file`.
- **Tool tables are not complete [reading].** `PLUGIN_OPTIONS` knows `--benchmark-only` (module
  `pytest_benchmark`), but `MODULE_GROUPS` and `env.TOOL_MODULES` do not list it, so
  `env.check-tools` never reports a missing `pytest-benchmark` and `hint("pytest_benchmark",
module=True)` is the generic `DEFAULT_HINT`. Other options of the plugin
  (`--benchmark-compare`, `--benchmark-disable`) and of `pytest-cov` (`--no-cov`, `--cov-branch`,
  `--cov-config`) are not in `PLUGIN_OPTIONS`.
- **`null` is read as "not set" [reading].** `get_config` drops a `None` for every key whose default
  is an `int` (to accept the `None` that `default_config` registers). `unit_timeout: ~` or
  `xdoctest: null` in `invoke.yaml` is therefore the default, silently, instead of the error that
  `unit_timeout: "abc"` gets. Tell the two apart: the registered `None` comes from the defaults
  level, not from the project file (`config._defaults` is not public, so test the value after the
  merge, or register a sentinel object instead of `None`).
- **`_project_version` [reading].** `release._project_version` calls `read_text()` without an
  encoding and lets a `TOMLDecodeError` escape as a traceback, whereas `_coverage_html_dir` (same
  file) handles it. Read with `encoding="utf-8"`; turn an invalid file into an `Exit` with the
  file name.
- **A dotted `import_name` imports its parent [reading].** `importlib.util.find_spec("a.b")` imports
  `a`. `_validate_import_name` accepts dots, and `_discover`/`_graph` promise to import nothing.
  Either reject dots, or find the package with `find_spec` on the first part and walk the
  directories.
- **`STEP_ERRORS` is a whitelist [reading].** `run_step` catches nine families of exceptions. The
  docstring says the point is to keep going after a bug, but an exception outside the list (a
  `Warning` turned into an error, a `StopIteration`, an `AssertionError`, a custom `Exception`)
  still ends a `--keep-going` run without the summary. `except Exception` is complete, and
  `KeyboardInterrupt` and `SystemExit` are not `Exception`, so they still stop the run.

## 2. Design

### 2.1 Four tables describe the same tools — low **[reading]**

A program or module is described in `check.STEPS` / `fix.STEPS` (`programs`, `modules`),
`env.TOOL_PROGRAMS` / `TOOL_MODULES`, `tools.PROGRAM_HINTS` / `PROGRAM_GROUPS` / `MODULE_GROUPS` /
`PLUGIN_OPTIONS`, and the step names in `config/_constants.py` (`CHECK_STEPS`, `FIX_STEPS`). Tests
keep them in line (the last review's 2.3 asked for that), but a new tool is still edited in five
places, and 1.7 shows that they already drift (`pytest_benchmark`).

Suggestion: one `Tool` record in `tools.py`: `Tool(name, kind="program"|"module", group=None,
hint=None, plugin_options=())`, and one `TOOLS: dict[str, Tool]`. `hint`, `not_found_message`,
`env.check-tools` (all of `TOOLS`) and `PLUGIN_OPTIONS` (derived) read it, and the steps keep naming
the tools they need. The `STEPS` registries could also carry the step name, so `CHECK_STEPS` is
`tuple(STEPS)`; the circular import (`config` cannot import `check`) is the reason it is not done, so
keep the constants and the test, or validate `check.tasks` at use time (in `check.all_`) instead of in
the config. That would also let a custom project register its own step.

### 2.2 `report_failure` plus `say` is `step` written by hand — low **[reading]**

Eight tasks write the same four lines: `with report_failure(c, "X..."):`, `say(c, "X...")`, the work,
and `say(c, "✅ ...")` after the block. They are `testing.benchmark`, `testing.doctest_markdown`,
`release.build`, `release.publish`, `doc.publish_dev`, `doc.publish_latest`, `env.create_venv` and
`env.update`, plus `imports.check_isolated`. `output.step(c, start, done)` is the same thing with
the start message written once and the done message inside the block. Make `done` optional
(`build` has none) and use `step` everywhere: 25 lines fewer, one wording, and no task can forget
the failure line. One catch: the done message of `doctest_markdown` and `publish` is computed from
a value of the block (`len(files)`, `dry_run`), so build the message before the block.

### 2.3 Namespace names and `configuration.py` — low **[breaking]**

Open since two reviews. `formatting`, `typecheck` and `testing` are exposed as `format`, `types` and
`test` through the `_MODULES` dict, and a hand-made collection needs the workaround in the
docstring of `__init__.py` (`Collection.from_module(testing, name="test")`). `configuration.py`
(task `config.show`) sits next to the package `config/` and the namespace `config`. Suggestion: a
`NAMESPACE = "test"` constant in each task module, read by `make_ns` and documented for
`Collection.from_module(module, name=module.NAMESPACE)`; rename `configuration.py` (for example
`show.py`). Do it in the same release as 2.1.

### 2.4 Rely less on private Invoke attributes — low **[reading]**

`configuration._origin` reads `_defaults`, `_collection`, `_system`, `_user`, `_project`, `_env`,
`_runtime`, `_overrides` and `_modifications` of `Config`, and `_check_project_root` reads
`_project_prefix`, both with `getattr(..., None)`. If a release of Invoke 3.x renames one, the
origin column is wrong without an error, and the guard of the working directory is switched off,
which brings back the silent `⏭️` skip that it was written to stop. `invoke>=3.0,<4.0` allows every
3.x.

Suggestion: keep the private reads (there is no public API for them), but add one integration test
per attribute that uses the real `Config` and fails with a message that names the attribute (the
suite has one for the subdirectory guard in `tests/integration/test_project.py`; add the origin
labels), run it in the `ci-test-deps` job against the newest Invoke, and make the guard fail closed:
if the context has a `Config` of Invoke but no `_project_prefix`, treat it as unknown and say so in
`config.show`, not as "ok".

### 2.5 `imports.check-isolated` — low **[reading]**

Open since two reviews. The output is now a summary, but the task still starts one interpreter per
module (a package of 300 modules is 300 processes, about 20 ms each at best, seconds with heavy
imports). One worker (`python -m invoke_tasklib._discover --import-each`) that spawns the fresh
interpreters itself, or runs `importlib` in `multiprocessing` with the `spawn` start method and
a pool, would give the same guarantee faster, and the task could print the progress once. It is
also not a `check.all` step; add it as `isolated` if it becomes fast enough. See 1.3 for the
`-I` question.

### 2.6 The type checker is fixed — low **[reading] [breaking]**

`types.check` runs `ty` (pre-1.0: `ty>=0.0.96,<1.0`) and, with `--complete`, `pyright`; `mypy` is
not an option and the `types` step of `check.all` needs `ty`. A downstream project that uses
`mypy` or `pyright` alone has to exclude the task. Suggestion: `tasklib.types.checker` (`ty`,
`pyright` or `mypy`, default `ty`) and a step that follows it; or at least let `--complete` skip
`ty`. Also decide whether a tool at `0.0.x` should be the default of a library for other projects
(each `ty` release can add errors to every downstream `check.all`); a `tasklib.types.checker` with
the default `pyright` would be the conservative choice for a `0.1.0`.

## 3. Documentation, tests and CI

### 3.1 `inv test.doctest` fails on `main` because of the review file — medium **[verified]**

```text
$ .venv/bin/inv test.doctest
📚 Found 46 markdown files
File "review/suggestions.md", line 160, in suggestions.md  (and lines 162, 163, 240, 242)
***Test Failed*** 5 failures.
❌ Failed: Running doctests on markdown files
```

`doctest_markdown` finds every tracked `.md` file, including `review/suggestions.md`, whose examples
were written as `>>>` to show a bug that is now fixed. `CLAUDE.md` says the doctests pass on `main`,
and `ci-doctest.yaml` runs the same task. This review uses `text` blocks without the prompt, so
it fixes the failure; to keep it fixed, add one line to `CLAUDE.md` (a review shows its examples as
`text`, not as `pycon`), or let `doctest_markdown` skip `review/` (it is not documentation, and
`tasklib.paths` could get a `doctest_exclude` list). The first is a line; the second is a feature.

### 3.2 The `mike` integration tests never run in CI — medium **[reading]**

Eight tests of `tests/integration/test_doc.py` skip when `mike` is missing (13 skips in total here).
The `docs` group is installed only when the `docs-deps` input of `setup-uv-env` is `"true"`, and the
only workflows that set it are `ci-doctest.yaml` and `release-docs-publish.yaml`; `ci-test.yaml`
(which runs `inv test.all --cov`) does not. Nothing runs `pytest` with `mike` installed, so
`doc.publish-latest` and `doc.publish-dev` are tested only against a patched context in CI. That is
what the "patched behaviour needs an integration test" rule of `CLAUDE.md` is meant to prevent.

Suggestion: pass `docs-deps: "true"` in `ci-test.yaml` for the `ubuntu-latest` / latest-Python cell
(the `ci-doctest` job installs the group already, so the cost is one more sync). Make the skip loud:
use `pytest.importorskip`-style `skip` with a reason that names the group, and add a CI check that
the number of skips is not above an expected value (`--strict-markers` does not do that).

### 3.3 No benchmarks, and `check.all` is not run for pull requests — medium **[verified]**

Unchanged from the previous review: `tests/benchmarks/` does not exist, so the nightly
`ci-benchmark.yaml` runs `inv test.benchmark`, prints `⏭️ No 'tests/benchmarks' directory` and passes.
The job, the `pytest-benchmark` dependency and the task exist, and nothing is measured. The previous
review (commit `80300bf`, section 4.4) has the full plan; the short version:

- add `tests/benchmarks/` with `test_<area>_benchmark.py` files for the pure-Python hot paths:
  `_graph.import_graph` and `find_cycles` on generated graphs of 1,000 and 10,000 modules
  (`default_rng(0)`), `runner.build_command` with many paths, `_files.find_files` on a generated
  tree, `config.get_config` on a full config, `make_ns()` and `import invoke_tasklib` (start-up time
  of every project that uses the library);
- the nightly job compares with the previous run (`--benchmark-compare-fail=mean:50%`) and uploads
  `.benchmarks`;
- `test.benchmark` exits non-zero when it is asked for explicitly and the directory is missing.

Also, the pull-request jobs run the tasks one by one (`test.all`, `lint.check-python`,
`format.check-python`, `types.check`, `imports.check-cycles`, `test.doctest`, `release.build`), and
`check.all` with its default steps runs only in the nightly job and with `--only shell,spelling`.
A break of the composite task (a renamed step, a wrong tool list) is found a day late. One
`uv run inv check.all --keep-going` job on pull requests would run the product as a user does.
Do the benchmarks before any change of 2.1 or `project_files` to measure it.

### 3.4 Tests — low **[verified]**

Strengths: 2,702 tests in 15 s, 100% line and branch coverage, a real integration suite (git, a
stripped `PATH`, the real `inv`, quoting), `filterwarnings = error`, and the rules of `CLAUDE.md`
applied almost everywhere. The `ast` scan finds no test with two asserts, no loop, no local import
and no `pytest.raises` followed by more than one `assert`. What is left:

- One `pytest.raises` has no `match=`:
  `tests/unit/config/test__resolve.py::test_load_config_exit_code_is_2_from_a_subdirectory`.
  (The other hit of the scan, `test_release.py::testpypi_token`, is a fixture.)
- `_context` is still defined in 13 unit modules next to `tests/helpers.make_context`. The previous
  review asked to use the helper; it was done for `clean` and `check` only. Where the default
  differs, `_context = partial(make_context, ...)` in the module is enough.
- No property test: `shlex.split(build_command(...))` round-trips the words, and `find_cycles`
  agrees with a brute-force reachability on small random graphs (`default_rng(0)`). `grep` finds no
  `hypothesis` and no `default_rng` in `tests/`. These are the two modules with real algorithms.
- Each fix of section 1 needs its regression test, checked with `git stash push src`. For 1.1, 1.2,
  1.3 and 1.4 add an integration test with the real tool, not only the command list (the unit test
  cannot show what `uv` or `python` really does).

## 4. Packaging and repository

- **`feu[all]`** in the `dev` group is used only by `dev/generate_versions.py`; check whether every
  contributor needs it **[reading]**.
- **Version**: `0.1.0a0`, `Development Status :: 3 - Alpha`. The breaking items (1.2 if the
  lookup is exposed, 2.1, 2.3, 2.6) belong to one `0.2.0` or to `0.1.0`, announced in the notes.
- **`tasks.py` of this repository** adds `build-package` for an external action; the comment
  explains why. Keep it, and remove it the day the action calls `release.build`.
- **`Makefile` and `inv`** both run the linters of the repository (`make lint` for yaml, shell,
  markdown; `inv lint.*` for Python). They do not overlap, but `CONTRIBUTING.md` should say which
  one a contributor runs before a pull request, in one table **[reading]**.

## 5. Suggested order of work (one PR each, as in `CLAUDE.md`)

1. Merge this review (fixes 3.1), then the line in `CLAUDE.md` about the examples.
2. `uv.lock` optional (1.1) and the `PATH` of the environment (1.2), with their integration tests.
3. `release.build -I` (1.3) and the publish environment (1.4).
4. Coverage outputs (1.5), shell format check (1.6), the minor list (1.7) in small PRs.
5. `docs-deps` in `ci-test.yaml` (3.2) and the PR job for `check.all` (3.3).
6. `step` everywhere (2.2), then the `Tool` registry (2.1).
7. Benchmarks (3.3) before any performance-driven change; the tests of 3.4 along the way.
8. As one release: namespace names (2.3), checker option (2.6), `check-isolated` worker (2.5), and
   the private-attribute canaries (2.4).

## What was and was not done

- Done: all of `src/` was read; the baseline ran (`pytest`, coverage, `ruff`, `ty`, `inv
test.doctest`); the doctest failure (3.1), the missing lock file (1.1), the unactivated
  environment (1.2) and the `python -c` path (1.3) were reproduced with the real `inv`, `uv` and
  `python` on the repository or on a probe project (kept outside the repository); the tests were
  scanned with `ast`; the skipped tests were listed with `pytest -rs`; the workflows were searched.
- Not done: no source file or test was changed. Items marked **[reading]** were not run and need a
  second look before a pull request; in particular 1.4 (does `uv publish` read the inherited
  variable? try `uv publish --dry-run`), 1.5, and 2.6. `release.publish` was not run, nothing was
  uploaded, the workflows were not read in full, CI results were not looked at, and `docs/` was
  not reviewed.
