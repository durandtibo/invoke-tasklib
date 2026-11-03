# Review of `invoke-tasklib` — suggestions

This review replaces the one committed in `3e81371` (#117). Most of that review has been acted on
since (the shared runner, `say` instead of `logging`, `make_ns`, frozen-dataclass config, key
validation, `--args`/`--paths`, `import_name`, the `_discover` module, `doc.build`, ...), so it was
redone from scratch on the current code. The old text stays available in the git history.

## Scope and method

Everything tracked in the repository was read: `src/` (all 16 modules), `tests/` (all 18 test
modules and the `conftest.py`),
`tasks.py`, `dev/`, `pyproject.toml`, `invoke.yaml`, `.pre-commit-config.yaml`, `README.md`,
`CONTRIBUTING.md`, `CLAUDE.md`, `SECURITY.md`, all the pages of `docs/`, `.github/` (every workflow
and composite action, `GUIDELINES.md`, templates) and `.make/` (vendored, read only to see how it
interacts with the repo).

Baseline when reviewed (`main` at `ccc407d`, nothing modified in the repository except this file):

| Check                                             | Result                                                         |
| ------------------------------------------------- | -------------------------------------------------------------- |
| `pytest tests`                                    | 524 passed in 1.3 s, 100% line and branch coverage             |
| `ruff check` / `ruff format --check` / `ty check` | clean                                                          |
| `inv test.doctest`                                | **2 failed**, 25 passed (see 1.1)                              |
| CI runs on `main`                                 | not assessable: the last 30 runs of `ci.yaml` are all `queued` |

Legend:

- **[verified]**: reproduced in this checkout (with the real `inv`, in a throw-away project under
  the scratchpad, or by running the tool). The command is given or obvious.
- **[reading]**: deduced from the code, not reproduced.
- **[breaking]**: changes a documented behavior, signature or config key. Breaking changes are
  welcome per the request, so they are proposed where they give the better design.
- Severity: **high** (wrong result, crash, or a promise the project makes that is false),
  **medium** (real friction or a latent bug), **low** (polish).

## Summary: what to do first

| #    | Finding                                                                                               | Sev.   |
| ---- | ----------------------------------------------------------------------------------------------------- | ------ |
| 1.1  | `inv test.doctest` fails on `main`; nothing in `check.all` or the unit tests runs it                  | high   |
| 1.2  | `say` raises `UnicodeEncodeError` on a non-UTF-8 terminal, killing every task                         | high   |
| 1.3  | Many commands interpolate config values and file names unquoted (breaks on a space, injectable)       | high   |
| 1.4  | A string where a mapping/list is expected gives nonsense errors (`'f', 'o'`, `'c', 'd', 'o'`)         | medium |
| 1.5  | Unknown top-level `tasklib` keys are ignored; several values are not type-checked                     | medium |
| 1.6  | `clean` misses `src/*.egg-info`, and removes `build`/`dist`/`site` unconditionally                    | medium |
| 1.7  | The "program not found" hint is wrong for `uv`, `codespell`, `shellcheck`, `shfmt`                    | medium |
| 1.8  | `lint.check-spelling` cannot work in this repo; `env.show-python-config` exits 1                      | medium |
| 1.12 | All 8 admonitions of the docs render as an empty box (indentation lost)                               | medium |
| 1.14 | The 72-character limit is documented as enforced by ruff, but `W505` is ignored (37 violations)       | medium |
| 2.1  | `imports.check-cycles` does not detect cycles; it detects import-order failures                       | medium |
| 2.2  | `--args` is missing on half of the tasks (cannot ignore a CVE, change the docs port, ...)             | medium |
| 3.1  | The integration tests are 5 tests; the real runner, YAML loading and `inv --list` are never exercised | high   |

A suggested order of work, as small stacked PRs, is in section 7.

---

## 1. Bugs and correctness problems

### 1.1 The doctests fail on `main` and nothing would catch it — high **[verified]**

```text
$ .venv/bin/inv test.doctest
FAILED src/invoke_tasklib/_discover.py::main:0
FAILED src/invoke_tasklib/testing.py::_directory_exists:0
2 failed, 25 passed
```

Both examples print something _and_ return a value (`main(...)` returns `0`,
`_directory_exists(...)` returns `False`) and write the returned value in the expected output.
That is the standard `doctest` semantics, but `test.doctest-src` runs `pytest --xdoctest`, and
xdoctest compares the printed output only, so the trailing `0` / `False` is "missing".

Why it went unnoticed, in order of importance:

1. `check.all` (the "run before you push" command) does not run any doctest.
2. The unit tests do not run the doctests of `src/` either, so 100% coverage says nothing about
   the examples.
3. `CLAUDE.md` states that the doctests pass on `main`, so an agent will assume a failure is its
   own. The last 30 `CI` runs listed by `gh run list --workflow ci.yaml` are all `queued`, so the
   `ci-doctest.yaml` job that would have shown it has not reported anything.

There is a deeper issue behind the two failures: the project runs the examples of `src/` with
**xdoctest** and the examples of the Markdown files with the **standard `doctest`**
(`python -m doctest`). The two engines disagree on what an expected output is (print + return
value, `...` handling, `# doctest:` versus `# xdoctest:` directives). The docstring examples have
to be written for one engine and the Markdown for the other, and nothing says so.

Proposal:

- Fix the two examples (assign the result: `_ = main([...])`, or print it).
- Pick **one** engine for both. Simplest: `pytest --doctest-modules --doctest-glob='*.md'` with the
  `ELLIPSIS`/`NORMALIZE_WHITESPACE` flags in `doctest_optionflags`, one process, one report, one
  semantics. If xdoctest is kept for `src/`, document the rule in `CONTRIBUTING.md` and use
  xdoctest-compatible Markdown too.
- Add `test.doctest-src` to `check.all` (see 2.4) and add a unit/integration test that runs the
  doctests of the package, so a broken example fails `pytest tests` and not only CI.
- Fix `CLAUDE.md`, which currently claims something that is false.

### 1.2 `say` crashes on a terminal that cannot encode the emojis — high **[verified]**

```text
$ PYTHONIOENCODING=ascii inv clean.pycache
...
  File ".../invoke_tasklib/output.py", line 36, in say
    stream.write(f"{message}\n")
UnicodeEncodeError: 'ascii' codec can't encode character '\U0001f9f9' in position 0
```

Every message starts with an emoji. With `LANG=C`, `PYTHONIOENCODING=ascii`, a Windows legacy code
page, or some CI log collectors, the very first `say` aborts the task with a traceback _before_
the real command runs. A progress message must never be able to fail a task.

Proposal (one change in `output.py`):

- Catch `UnicodeEncodeError` and retry with `message.encode(encoding, "replace")`, or strip the
  leading emoji when `stream.encoding` cannot encode it.
- Add a switch to turn the emojis off: `tasklib.ui.emoji: false` (and/or honor `NO_COLOR`/`CI`).
  The emojis are also hard-coded in the tests (`test_clean`, `test_imports` assert the whole text),
  so move them to one table of constants (`OK = "✅"`, ...) used by `say` helpers such as
  `say_done(c, msg)`; the 84 `say(...)` calls of `src/` all carry a literal emoji today, so this
  also makes the switch trivial.
- Consider `--quiet`: `say` ignores Invoke's `--hide` and `run.hide`.

### 1.3 Config values and options are interpolated unquoted into shell commands — high **[verified]**

`runner.build_command` quotes everything, and the tasks that use it (`format`, `lint`, `types`,
`test.unit`/`all`/`integration`/`functional`) are safe. These are not:

| Where                                                             | Interpolated, unquoted                                                 |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `doc.build`, `doc.serve`, `doc.publish-dev`, `doc.publish-latest` | `paths.docs_config`                                                    |
| `testing.doctest_markdown`                                        | every Markdown file name                                               |
| `testing.doctest_src`                                             | `paths.src`                                                            |
| `testing.benchmark`                                               | `paths.benchmarks`                                                     |
| `env.install`                                                     | each `--group` value (CLI and config)                                  |
| `env.create_venv`                                                 | `package.python_version` (safe: the regex allows only digits and dots) |
| `formatting` (shell tasks)                                        | none (constants), fine                                                 |

Reproduced:

```text
$ inv test.doctest-markdown          # with a file "my docs/a b.md"
FileNotFoundError: [Errno 2] No such file or directory: 'my'
$ inv doc.build                      # paths.docs_config: "d d/mkdocs.yml"
Error: Invalid value for '-f' / '--config-file': 'd': No such file or directory
$ inv env.install --groups 'dev;echo INJECTED'
uv sync --locked --all-extras --group dev;echo INJECTED
INJECTED
```

The injection is only "you attack yourself" for a CLI flag, but `invoke.yaml` is data that can come
from a pull request, and `SECURITY.md` currently documents the whole class as a known limitation
("inserted into shell command lines without quoting"). Fixing it removes the caveat.

Proposal: build **every** command with `build_command` (add a `build_command(program, *words)`
form so fixed options and values go through `shlex.quote` too), then delete the paragraph of
`SECURITY.md`. A ruff/grep rule or a unit test that fails when a task passes an f-string with a
`{` to `run(...)` keeps it that way. For the Markdown doctests, pass all the files to **one**
`python -m doctest f1 f2 ...` call (it accepts several files), which is faster (38 files here) and
reports every failing file at once instead of stopping at the first.

### 1.4 A string where a mapping or list is expected gives a nonsense error — medium **[verified]**

```text
tasklib:
  paths: foo            ->  Unknown keys 'f', 'o' in 'tasklib.paths'. Valid keys: ...
make_ns(exclude="doc")  ->  Unknown task or namespace ['c', 'd', 'o']. Valid names: ...
```

Both iterate over the characters of a string. `_check_keys` calls `set(user)` on whatever the
section is, and `make_ns` calls `tuple(exclude)`. The `make_ns` case is a likely typo (one name
instead of a list).

Proposal: in `get_config` check that each section is a mapping (`'tasklib.paths' must be a
mapping, got 'foo'`); in `make_ns` accept a bare `str` as one name (`exclude = (exclude,) if
isinstance(exclude, str) else tuple(exclude)`), or reject it with a clear message.

### 1.5 Unknown top-level keys are ignored and several values are not type-checked — medium **[verified]**

- `tasklib: {pakage: {...}, package: {...}}` <!-- codespell:ignore pakage --> is accepted silently; `_check_keys` is applied to the
  four sections but not to the top level. A typo of a whole section (`path:`, `group:`, `tests:`)
  is the most likely typo of all.
- `package.name: ["a"]` is reported as "`import_name` must be a Python module name", blaming the
  wrong key. A non-string name should be rejected where it is read.
- `paths.src: ""` is accepted and kept (`test_get_config_empty_src_is_kept` asserts it) and then
  passed to `docformatter` as an empty argument; `paths.tests: 5` becomes `"5"`. Every `paths.*`
  value should be a non-empty string.
- The `test.cov_fail_under` bound is `>= 0` but nothing rejects `> 100`.

Proposal: one `_validate_str(section, key, value)` helper next to the existing `_validate_*` ones
(as the project instructions ask), and `_check_keys("tasklib", user, ("package", "paths", ...))`.

### 1.6 `clean` misses some artifacts and deletes some project directories — medium **[verified]**

- `DIR_GLOBS = ("*.egg-info",)` is relative to the root only. With a `src` layout the metadata is
  `src/<pkg>.egg-info`, which is never removed (reproduced: `mkdir -p src/demo.egg-info; inv clean`
  leaves it).
- `build`, `dist` and `site` are removed unconditionally. In some projects `build/` holds scripts
  and `site/` holds content. At least `site` should only be removed if `docs/mkdocs.yml` exists
  (that is what produces it), and the list should be configurable
  (`tasklib.clean.dirs`/`files`, or "extra" entries).
- Not cleaned although the repo's own tools create them: `.coverage.*` (parallel coverage data),
  `.tox`, `.nox`, `.hypothesis`, `.ipynb_checkpoints`.
- There is no `--dry-run`, and no way to see what would be removed before it is.
- `_remove_dir` calls `shutil.rmtree` on anything for which `is_dir()` is true; a symlink to a
  directory makes `rmtree` raise [reading, not reproduced]. Use `path.is_symlink()` first.
- `_remove_dir` and `_remove_file` have no docstring, which `CLAUDE.md` forbids ("every function,
  public or private").

### 1.7 The "program not found" hint is wrong for several programs — medium **[verified]**

`runner.check_program` gives one message for every missing program: _Install the project tools
with `invoke env.install`_. That is false or circular for:

| Program                  | Why the hint is wrong                                                                                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv`                     | `env.install` itself runs `uv`; the hint is circular                                                                                                  |
| `shellcheck`, `shfmt`    | not Python packages; `env.install` never installs them (the docs say so)                                                                              |
| `codespell`              | not in this repo's `dev` group (reproduced, see 1.8)                                                                                                  |
| `pytest` (and `doctest`) | run as `python -m pytest` with an absolute interpreter path, so the check is skipped and the user sees Python's `No module named pytest` with no hint |

It also only looks at the first word, so `find ... | xargs -0 -r shellcheck --` is never checked
(a missing `shellcheck` surfaces as an `xargs` error, or as a silent success when no `.sh` file
exists).

Proposal: a small table `PROGRAM_HINTS: dict[str, str]` (`uv` -> the installer URL, `shellcheck`
and `shfmt` -> `brew install` / `apt install`, others -> the dependency group) used by
`check_program`; check the program of every stage of a pipeline, or run the stages separately from
Python; check `import pytest` with `importlib.util.find_spec` before running `python -m pytest`.

### 1.8 `lint.check-spelling` and `env.show-python-config` fail in this very repo — medium **[verified]**

- `inv lint.check-spelling` -> `'codespell' was not found on the PATH. Install the project tools
with invoke env.install`. `codespell` is not in the `dev` group of `pyproject.toml` (the
  pre-commit hook has its own environment), so the task added to the library cannot run in the
  repository that ships it, and the suggested fix does not fix it. Add `codespell` to `dev`.
- `inv env.show-python-config` exits 1 when no `python` is on the `PATH` (the last command,
  `command -v python`, returns 1), after having printed everything else. Use `warn=True`, or drop
  the line: `uv python find` already answers the question.

### 1.9 `doc.publish-latest` and `doc.publish-dev` — medium **[reading]**

- `latest` can move **backwards**: publishing a backport (`1.1.5` after `1.2.0` exists) deploys
  `1.1` with the alias `latest` and sets it as the default. Compare with the versions already
  published (`mike list --json`) and refuse, or require `--force`.
- `from feu.local_git import ...` is a lazy import with no `try`: without `feu` the user gets a
  `ModuleNotFoundError` traceback, and the troubleshooting page documents that traceback as the
  expected behavior. Convert it to `Exit` with the install hint, like the other errors.
  `feu[all]` is a heavy dependency for one function (reading the last version tag); one `git`
  call through `run(...)` would remove both the dependency and the failure mode, leaving
  `dev/generate_versions.py` as the only user of `feu`.
- `publish_dev` runs `mike delete main` (with `warn=True`) before `mike deploy`; `deploy`
  already replaces an existing version, so the delete is redundant and, if the deploy fails,
  removes the version from the local `gh-pages`.
- Both tasks `--push` with no confirmation and no `--dry-run`/`--no-push`.

### 1.10 `env.*` side effects and redundancies — medium **[reading]**

- `env.update` runs `uv tool upgrade --all`, which upgrades **every uv tool the developer has
  installed globally** (not only the project's). A project task should not change the user's
  machine-wide tools. Remove it (document `uv tool upgrade` for people who want it) or make it an
  opt-in flag.
- `env.update` runs `pre-commit autoupdate`, which fails (exit 1) in a project without a
  `.pre-commit-config.yaml`; the task is unusable there. Check the file exists or add
  `--no-hooks`. `bot-update-deps.yaml` also calls `env.install --groups dev,docs` right after
  `env.update`, which already installed `dev,docs`.
- `env.install` runs `uv sync --locked` and then `uv pip install -e .`. `uv sync` already installs
  the project (editable) so the second command is redundant, and `uv pip install` is outside the
  lock. It was already noted in the previous review and is still there (the CI composite action
  does the same, see 6.5).
- `env.create_venv` clears an existing `.venv` with no confirmation (documented, but a
  `--yes`/prompt for an existing environment would be kind), and the default
  `python_version` is the constant `"3.14"`, which becomes wrong the day 3.14 is not what the
  project targets. Better defaults: `.python-version`, then `requires-python` of `pyproject.toml`,
  or omit `--python` and let `uv` choose.
- `.make/uv.mk:setup-venv` runs `uv venv --clear` and then `uv run inv env.create-venv`, which
  clears the environment a second time.

### 1.11 Test tasks — medium **[reading]**

- `test.unit` fails (pytest error 4) when `tests/unit` does not exist, while `integration` and
  `functional` skip with a message. A project with a flat `tests/` is the common case. Fall back to
  `paths.tests` or skip, consistently.
- `--cov-report html --cov-report xml --cov-report term` is hard-coded: HTML and XML are always
  generated (slow on large suites) and `coverage_report` hard-codes `htmlcov/`. Make the reports a
  config list (`test.cov_reports`).
- `integration --cov` and `functional --cov` always append, so run alone they merge into whatever
  `.coverage` is on disk (the docs warn about it). Prefer an explicit `--cov-append` flag, or have
  `test.all --cov` run the three scopes with a single `coverage erase`.
- `coverage html` / `coverage report` run `coverage` from the `PATH` while pytest uses
  `python_executable()`; use `python -m coverage` for consistency (same venv as the tests).
- `doctest-markdown` walks `site/`, `build/`, `dist/`, `.tox`, `.mypy_cache` (only four names are
  excluded) and `rglob`s into `.venv` before filtering. Use `git ls-files '*.md'` or prune while
  walking (as `clean._find_pycache_dirs` already does).
- `benchmark` has no `--args`, no timeout and requires `pytest-benchmark`, which is not in the
  tools table.
- `--timeout` requires `pytest-timeout` and `--cov` requires `pytest-cov`; neither is in the
  external tools table of `uguide/index.md` (`xdoctest` is covered by the `test.xdoctest` switch).
  A project that has no `pytest-timeout` gets `unrecognized arguments: --timeout`.

### 1.12 All the admonitions of the docs are broken — medium **[verified]**

Every `!!! warning` / `!!! note` of the user guide (8 of them: `doc.md`, `lint.md`, `release.md`,
`env.md` x2, `format.md` x2) has its body at column 0:

```text
!!! warning
This clears any existing `.venv`.
```

Rendered with the `admonition` extension (what `mkdocs.yml` enables), this gives an **empty
warning box followed by a normal paragraph**; the text must be indented by four spaces. They were
indented when written (`git log -S` shows the original), so something removed the indentation. The
likely culprit is `prettier --write '**/*.md'` run by `make format-markdown` (and the weekly
`bot-format-files.yaml`), which does not know the syntax. This will happen again.

Proposal: restore the indentation and protect it: `<!-- prettier-ignore -->` before each block, or
a `.prettierignore` for `docs/docs/uguide`, or move to a syntax prettier keeps (`> **Warning**`).
`mkdocs build --strict` does not catch it, so add a small test over `docs/docs/**/*.md` that fails
on a `!!! x` line not followed by an indented line.

### 1.13 The README example for custom tasks does not work — medium **[verified]**

```python
from invoke_tasklib import make_ns

from . import my_custom_task  # <- ImportError
```

Invoke imports `tasks.py` as a top-level module, so the relative import fails with
`ImportError: attempted relative import with no known parent package`. Use an absolute import or
define the task in the file. Since `test.doctest-markdown` only runs `>>>` blocks, such a
snippet is never executed; consider a test that compiles and runs the fenced `python` blocks of
the README in a temporary project.

### 1.14 The 72-character limit is not enforced although the docs say it is — medium **[verified]**

`CLAUDE.md` and `CONTRIBUTING.md` say "`ruff` enforces it", and `pyproject.toml` sets
`max-doc-length = 72`, but `W505` is in `lint.ignore`. Running the rule shows **37 violations**
(`env.py` 9, `testing.py` 6, `formatting.py` 3, `lint.py` 2, `doc.py` 2, `release.py`,
`runner.py:87` (94 characters), `tests/integration/test_imports.py:20`, ...). `docformatter` wraps
prose to 72 but not code in `pycon` blocks or sections such as `Args:` continuation lines.

Proposal: remove `W505` from the ignore list and fix the 37 lines (a single formatting PR), so the
rule becomes true. Two private functions (`clean._remove_dir`, `_remove_file`) also lack the
mandatory docstring; ruff's `D103` skips private names, so enforcing the rule mechanically needs a
small test that walks the AST of `src/` and lists the functions without a docstring.

### 1.15 Environment-variable overrides of the config silently do nothing — low **[verified]**

Invoke maps `INVOKE_FOO_BAR` onto the config only for keys that already exist in the defaults
tree. The `tasklib` section has no defaults registered with Invoke (they live in `config.py`), so
`INVOKE_TASKLIB_PATHS_SRC=zzz inv test.doctest-src` still uses `src/<name>`. CI users will try
this first. Either document that only `invoke.yaml` (and `-f`/`INVOKE_RUNTIME_CONFIG`) works, or
register the defaults with `ns.configure({"tasklib": {...}})` so that environment variables, the
user-level config file and `--print-config` see them (and `get_config` can drop its own merge).

---

## 2. Design and API

### 2.1 `imports.check-cycles` checks import order, not cycles — medium **[reading]**

The task imports every module in a fresh interpreter. That catches a module that fails when
imported first, which is _a_ symptom of a cycle, but:

- A failing import is reported as the raw traceback of the subprocess; the task never says "cycle".
  A missing optional dependency, a syntax error or a `ModuleNotFoundError` is reported the same way
  and looks like a cycle.
- A real cycle that works in every import order (for example two modules that import each other
  lazily, or only for type annotations) is not reported, although the task name promises it.
- It costs N+1 interpreters; for a package that imports `torch` or `pandas` at the top level this
  is minutes.

Proposal: build the graph statically with `ast` (the modules are already discovered without
importing), find strongly connected components (Tarjan, ~30 lines) and print the cycle path
(`a -> b -> a`), ignoring imports under `if TYPE_CHECKING:` and inside functions (configurable).
Keep the isolated-import check under another name (`imports.check-isolated`) if it is useful.
This is also faster, deterministic and needs no subprocess, which makes `_discover` and the shell
quoting of `python -c` unnecessary. **[breaking]** (different results).

### 2.2 `--args`/`--paths` are missing on half of the tasks — medium **[reading]**

The options are on `format`, `lint`, `types` and the pytest tasks, but not on: `security.audit`
(cannot pass `--ignore-vuln <id>`: one accepted advisory makes the task permanently red),
`doc.serve` (cannot choose `--dev-addr`), `doc.build`, `release.build`, `format.check-shell`,
`format.fix-shell`, `test.benchmark`, `test.doctest*`, `test.coverage-report` (`--fail-under`).
`uguide/index.md` also lists the tasks that have the options and forgets `lint.check-spelling` and
`lint.pre-commit`, which do.

Proposal: one decorator (`@tool_options`) that adds `args`, `paths` and their `help`, so adding a
task cannot forget them, and a unit test over `ns.task_names` that lists the exceptions explicitly.

### 2.3 `release.pypi` cannot be used with Trusted Publishing — medium **[reading]** **[breaking]**

The repository releases through Trusted Publishing (`release-pypi.yaml`), but `release.pypi` exits
unless `PYPI_TOKEN`/`UV_PUBLISH_TOKEN` is set, so the task cannot do what the project itself does.
It also lacks the guards one expects of an irreversible action: no `--dry-run`, no way to target
TestPyPI (`uv publish` has an option for the index or the publish URL; check the exact flag), no
check that the working tree is clean, that `HEAD` is a tag, or that the version of
`pyproject.toml` matches the tag.

Proposal: rename to `release.publish`; accept no token when running in GitHub Actions with
`id-token` (let `uv publish` use `--trusted-publishing always`); add a TestPyPI option, `--dry-run`
and a `--yes` confirmation outside CI; or remove the task and keep only `release.build`. The `tasks.py`
alias `build-package` could then be `ns.add_task(release.build, name="build-package")` (instead of a
wrapper function whose docstring is wrapped in the middle of a hyphen and names an action,
`durandtibo/pypi-release-action`, that the workflow no longer uses) [reading].

### 2.4 `check.all` is smaller than "the checks of the project" — medium **[reading]**

It runs 6 steps and stops at the first failure, so a contributor learns about problems one at a
time. It leaves out what the repo's own CI checks: the doctests (1.1), `format.check-shell`,
`lint.check-spelling`, `doc.build`, `security.audit`. It takes no option.

Proposal: `--keep-going` (run all, print a summary, exit 1 if any failed; the default for local
use), `--skip`/`--only`, and a config list `tasklib.check.tasks` so a project chooses its set. The
CI jobs (`ci-format`, `ci-lint`, ...) then stay separate only for parallelism.

### 2.5 The config schema is declared five times — medium **[reading]**

Adding a key today means editing: the `DEFAULT_*` dict, the dataclass, the `_check_keys` call, the
merge line, the constructor call, a `_validate_*` call, the `config.md` table, the README block
and `architecture.md`. The docs have drifted exactly there (the `test` section is missing from the
README and from the `config.md` example block).

Proposal: one declarative table, e.g. a dataclass with `field(metadata={"validate": ..., "doc":
...})` per key, from which `_check_keys`, the defaults, the error messages, the `config.md` table
and a JSON schema (`invoke tasklib-schema`, for editor completion of `invoke.yaml`, the "future
direction" of `architecture.md`) are generated. Also:

- store `groups.*` as a tuple (today they are joined into a comma-separated string by
  `_normalize_groups` and split again in `env.install`);
- load the config once per task (`_run_pytest` calls `load_config` again after its caller did);
- a `Config` section object could expose `.as_dict()` for `inv --print-config`-style debugging;
- `EXCLUDED_DIRS` lives in `config.py` but is not configuration and is not configurable; move it
  to a `paths`-like module and let `tasklib.exclude` extend it.

### 2.6 `uv` is a hard requirement but the install docs offer `pip` — low

`env.*`, `release.*` and `security.audit` call `uv`; `ci`/`Makefile` assume it. The README and
`get_started.md` present `pip install invoke-tasklib` as an equal alternative and never say that
most of the tasks need `uv`. State the prerequisite (and the `uv` install link) in the README
"Install" section and in the `uv` hint of 1.7.

### 2.7 `security.audit` — low **[reading]**

`uv run pip-audit` runs `uv run`, which first syncs the project environment (network, writes to
`.venv`) although the task is advertised as read-only, and it audits the _environment_ rather than
the lock file, so the result depends on what was installed last. Auditing the lock file
(`uv export --locked --no-emit-project | pip-audit -r ...`, or `pip-audit` on a lock export) is
reproducible and does not touch the environment. Verify the exact `pip-audit` flags before adopting.

### 2.8 Progress output API — low

Beyond 1.2: `say(c, "🔍 Checking: ...")` repeats an emoji, a verb and a final "complete" message in
every task (~45 call sites). A context manager `with step(c, "Checking spelling") as s:` that prints
the start line, the elapsed time and a success/failure line (and nothing but the failure with
`--quiet`) would cut each task by 2-3 lines and make the failure case visible (today a failed step
prints no "failed" line; the last message the user sees is the 🎨 start line, followed by the tool's
own error).

### 2.9 Public surface — low

- `ns` is still a shared, mutable singleton next to `make_ns()`. Since `make_ns` exists, consider
  deprecating `ns` (breaking, one release of `DeprecationWarning`) or building it lazily.
- `invoke_tasklib.__version__` does not exist; `verify-installed-package` prints a "version/module"
  but only the file. Add `__version__ = importlib.metadata.version(...)`.
- `runner`, `output` and the top-level `invoke_tasklib` module (`make_ns`!) have no page in
  `docs/docs/refs/`; the headline API is the only public function absent from the reference.
  Generate `refs/*.md` with `mkdocs-gen-files` so a new module cannot be forgotten.
- `check_program`, `build_command`, `run`, `say`, `load_config` are what a downstream custom task
  should use (the project's own instructions say so) but are not documented for users, only in
  `CLAUDE.md`. Add a "Writing a custom task" page; it also makes them a supported API.

---

## 3. Tests

The unit tests are tidy, fast and complete for what they check (100% coverage, 524 tests in 1.3 s).
The weak point is what they cannot see.

### 3.1 The integration tests are almost non-existent — high **[verified]**

`tests/integration/` has 5 tests (`imports.check_cycles` x2, the shell `find` command x3). The
project's own rule is that every patched behavior needs an integration test. What the unit tests
patch or bypass, and nothing exercises for real:

| Bypassed in unit tests                                      | Consequence                                                                                                            |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `Config(overrides=...)` instead of a real `invoke.yaml`     | YAML parsing (unquoted `3.10`, lists, anchors) is never tested; the config error messages are tested on Python objects |
| `MockContext` instead of the Invoke runner                  | `echo`, `pty`, `warn`, `hide`, `env` semantics, and 1.2 (encoding) are never run                                       |
| autouse patch of `shutil.which` and of `sys.executable`     | `check_program` against a real `PATH`; the hint logic of 1.7                                                           |
| a fake `feu` module in `sys.modules`                        | `doc.publish_latest` never meets the real `feu`                                                                        |
| `Path.rglob` monkeypatched globally                         | `doctest_markdown` never walks a real tree                                                                             |
| `_SubprocessContext` (integration) replaces Invoke's runner | even the integration tests skip the real runner                                                                        |

Add (all cheap, no network):

- **An end-to-end fixture project** in `tests/integration/` (`tasks.py` with `from invoke_tasklib
import ns`, an `invoke.yaml`, a tiny package, a tiny test) driven by `subprocess.run(["inv", ...])`:
  `inv --list` (assert the exact task names and that no summary contains backticks, see 4),
  `inv format.check-python`, `inv test.unit`, `inv clean`, and a bad `invoke.yaml` for each error
  message. This would have caught 1.2, 1.3, 1.4 and 1.13.
- `release.build` on a generated minimal project (skip if `uv` is absent), asserting the artifact
  that was verified is the one in `dist/`.
- `doc.publish_latest` in a `tmp_path` git repository with a real tag.
- A test that runs the doctests of the package and of the Markdown files (1.1).
- The same fixture project, run from the nightly "published package" workflow, instead of only
  importing the package: that is the test that matches what users do.

### 3.2 Duplicated helpers — medium **[verified]**

`_context(...)` is defined in 14 test modules and `_commands(...)` in 10 (near-identical bodies; a
few `_context` variants take extra arguments, for example `run=` in `test_imports.py`).
`development.md` teaches the copy-paste pattern. Move them to `tests/unit/conftest.py` fixtures (`make_context`,
`commands`) or `tests/helpers.py`, return a tiny wrapper with a `.commands` property (removes the
`assert isinstance(run, Mock)` boilerplate that exists only for the type checker), and update the
development guide.

### 3.3 Departures from the project's own testing rules — medium **[verified]**

A script over the AST of all tests lists 17 tests that do not have exactly one `assert` or
`pytest.raises`: `test_get_config_overrides` (4 asserts), `test_get_config_groups_overrides` (2),
`test_all_removes_artifact_dirs` (2), `test_pypi_passes_token_through_environment` (2),
`test_pypi_accepts_uv_publish_token` (2), and 11 tests that combine `pytest.raises` with an
`assert` after it (`test_check`, `test_doc` x4, `test_release`, `test_runner` x3,
`test_config`, `test__discover`). The second group is a legitimate pattern ("it raised _and_ nothing
ran"); either allow it in the rules or split with a fixture. The 17th, an integration test
(`test_check_cycles_passes_without_cycle`), has **no assertion at all** (it passes if nothing
raises); assert on the captured output. Other details:

- `tests/unit/test_doc.py` has a `from invoke_tasklib import doc` import placed _after_ the
  `if TYPE_CHECKING:` block, unlike every other module.
- The `test_dirs` fixture in `test_testing.py` starts with `test_`; rename it (`_project_dirs`) so
  it cannot be mistaken for a test.
- The `tests/` tree has no `conftest.py` at the root, so `tests/integration` cannot share fixtures
  with `tests/unit`.
- Whole-output literals: `test_ns_contains_expected_subcollections` checks the namespaces but
  there is no test with the **complete list of task names** (the rule asks for it); renaming or
  dropping a task (for example `clean.pycache`) passes the suite. Add one literal assertion.

### 3.4 Missing cases (regression tests for section 1) — medium

`config`: section that is not a mapping, unknown top-level key, non-string `name`, empty/non-string
paths. `make_ns`: bare-string `include`/`exclude`. `say`: an ASCII stream. `runner`: pipeline
with a missing second program; per-program hints. `clean`: `src/*.egg-info`, symlink to a directory,
`site` without `mkdocs.yml`. `doc`: a downgrade, a missing `feu`. `env`: duplicate groups
(`"dev,dev"` gives `--group dev --group dev`), `uv tool upgrade` absent. `testing`: `tests/unit`
missing. Per the project rule, each must be shown to fail without the fix.

### 3.5 Use the project's own gate on itself — low

`invoke.yaml` of this repo sets only the package name. Setting `test.cov_fail_under: 100` locks in
the 100% coverage that the repo already has (and dogfoods the option), and the `pytest` options in
`pyproject.toml` still carry `log_level = "DEBUG"` and `log_format`, left from the `logging` era
(nothing in `src/` logs anymore).

---

## 4. Documentation

Verified against the code. Items 1-6 are factual errors; the rest are gaps.

| Where                                                    | Problem                                                                                                                                                                                                                                                                                                                                                                                              |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/docs/dev/architecture.md`                          | Principle 1 and the data-flow diagram say `get_config` and `c.run(cmd, pty=True)`; tasks now use `load_config` and `runner.run` (echo, pty only on a terminal, program check). `runner`, `output`, `_discover` and `EXCLUDED_DIRS` are not described.                                                                                                                                                |
| `docs/docs/dev/development.md`                           | "Adding a New Task" step 3 says `get_config(c)`; nothing about `run`, `build_command`, `say`, `--args`/`--paths` or `help=`. Quality commands use plain `ruff check .` / `python -m pytest`, while `CLAUDE.md` uses `.venv/bin/...` on `src tests`. The docs commands need `uv sync --group dev --group docs`, but setup step 3 syncs only `dev`. The tree misses `_discover.py`, `dev/`, `review/`. |
| `docs/docs/uguide/imports.md`                            | "every module of `package.name`": it is `package.import_name`.                                                                                                                                                                                                                                                                                                                                       |
| `docs/docs/uguide/doc.md`                                | "Both tasks read `paths.docs_config`": there are four.                                                                                                                                                                                                                                                                                                                                               |
| `docs/docs/uguide/index.md`                              | "Passing Arguments" forgets `lint.check-spelling` and `lint.pre-commit`; the tools table misses `pyright`, `coverage`, `pytest-cov`, `pytest-timeout`, `xdoctest`, `mkdocs-material`; "Everyday Workflow" does not mention `check`.                                                                                                                                                                  |
| `README.md`                                              | "tasks rely on POSIX tools (`which`, `find`, ...)": `which` is no longer used. The configuration block has no `package.import_name` and no `test:` section.                                                                                                                                                                                                                                          |
| `docs/docs/get_started.md` and every `inv --list` sample | `clean.pycache` shows raw backticks (` ``__pycache__`` `) because the docstring summary uses RST markup that Invoke prints verbatim **[verified]**. Reword the summary, and extend the existing `test_task_summary_*` tests to forbid backticks.                                                                                                                                                     |
| `SECURITY.md`                                            | "inserted into shell command lines without quoting" is true only for some tasks (1.3); update when 1.3 is fixed.                                                                                                                                                                                                                                                                                     |
| `CONTRIBUTING.md`                                        | The docstring example uses `Example:` and `# doctest: +SKIP`; the code uses `Example usage:` with runnable `pycon` blocks. Does not mention `inv check`.                                                                                                                                                                                                                                             |
| `.github/GUIDELINES.md`                                  | The workflow/task table says `ci-format.yaml` runs `format.check-docstrings` and `format.check-shell`; it actually runs `format.check-python` and `lint.check-python`, and `make` targets for the shell part. It names `durandtibo/pypi-release-action`; the workflow uses `build-pypi-package-action`.                                                                                              |
| `CLAUDE.md`                                              | "All the tests pass on `main`" (the doctests do not, 1.1) and "ruff enforces [72]" (1.14).                                                                                                                                                                                                                                                                                                           |

Structural suggestions:

- **Generate the repeated tables.** The task list exists in the README, `docs/docs/index.md`,
  `uguide/index.md`, `get_started.md` (the `inv --list` output) and the per-page overview tables.
  They are maintained by hand (PRs #144 and #146 were exactly this sync) and have already drifted
  more than once. Generate them from `make_ns()` in `dev/` and check them in CI
  (`inv docs.check-tables`-style); `get_started.md` can be a doctest of `inv --list`.
- `mkdocs.yml`: add `strict: true`, a `validation:` block and `edit_uri`; CI then fails on broken
  links and missing references.
- There is **no changelog**, although `CLAUDE.md` tells contributors to update it and
  `pyproject.toml` points `Changelog` at GitHub releases. Several behavior changes since `0.0.x`
  (config returned as dataclasses, `say` replacing `logging`, `release.build` verification,
  `--args`, key validation) are recorded nowhere. Add `CHANGELOG.md` (Keep a Changelog) with
  migration notes, and require a line in the PR template.
- Add a page "Writing a custom task" (see 2.9) and one "Recipes" page (a project with no docs, with
  a flat layout, with a different test layout, in CI).

---

## 5. Packaging, configuration and tooling

- `pyproject.toml` `lint.fixable` repeats the whole `lint.select` list (the default is `["ALL"]`);
  `lint.unfixable = []` is the default too. `T20` forbids `print` (good: `say` is the only
  writer).
- `[tool.ty.src] include = ["src", "tests", "dev"]` but `[tool.pyright] include = ["src"]`: `types.check
--complete` checks two different trees. Align or document why.
- `feu[all]` (a heavy meta-package) is a `dev` dependency for one function and
  `dev/generate_versions.py`. See 1.9.
- `dev/generate_versions.py`: the module docstring still says "Adapted from coola's ..." and is
  wrapped in the middle of hyphens (`dependency- compatibility`, `nightly-test-\npackage-dep.yaml`);
  `dev/` is outside the `paths.src` docstring tasks, so it was never reformatted. Rewrite it.
- The sdist only contains `src` (hatch `only-include = ["src"]`, verified by building it): no tests,
  docs or `CHANGELOG`. Distribution packagers (conda-forge, Linux distributions) want to run the
  test suite from the sdist; add `tests` (and the changelog once it exists).
- `.make/shell.mk` (`make format-shell`, part of `make format`) runs `find .` with only `.make`
  excluded, so locally it descends into `.venv` and `shfmt -w` rewrites third-party scripts — the
  bug `formatting.py` fixed for `format.fix-shell`. The directory is vendored, so fix it upstream
  (`shared-makefiles`) or make the `Makefile` targets call `inv format.fix-shell`. Having two
  implementations of the same check (Makefile and tasks) is itself the problem the library exists
  to solve; CI uses the Makefile one for shell and the tasks for everything else.

---

## 6. CI and workflows

CI could not be assessed: the last 30 runs of `ci.yaml` are all in the `queued` state (stuck, not
failed). That alone deserves a look (runner availability, or `bot-cancel-stale-queued-runs.yaml`
cancelling what it should not). Observations from reading the workflows:

### 6.1 Dogfooding gaps

- `ci-doctest.yaml` / `build` validates the docs with `mike deploy --branch tmp-doc-build-1234`,
  which does not fail on broken links. The new `doc.build` task (`mkdocs build --strict`) is the
  right check, is cheaper and needs no git setup. Use it.
- `ci-format.yaml` runs `format.check-python` and **`lint.check-python`** (duplicate of
  `ci-lint.yaml`), never runs `format.check-docstrings`, and checks shell with `make` rather than
  `format.check-shell`. The docstring check only happens indirectly, through the pre-commit hook
  (which runs `docformatter --in-place`, so the failure is a modified file, not a readable report).
- `security.audit` and `lint.check-spelling` are never run in CI (the latter fails in the repo, 1.8).
- `ci-benchmark.yaml` runs nightly but there is no benchmark; after the skip message was added, the
  job is a green no-op. Remove it, or add one benchmark to give it a purpose.

### 6.2 Consistency

- Two `astral-sh/setup-uv` pins coexist (`bec219d...` v10.1.0 in `actions/setup-uv-env`,
  `68559e9...` v10.3.3 in `release-pypi.yaml` and `nightly-test-package.yaml`), and `ci-format.yaml`
  and `bot-update-deps.yaml` use a third setup action (`durandtibo/setup-venv-uv-action`).
- `setup-uv-env` runs `uv sync --group dev` (neither `--locked` nor `--frozen`, so a stale lock is
  silently re-resolved in CI) and then `uv pip install -e .` (redundant, 1.10). Use `uv sync
--locked`.
- `release-pypi.yaml` needs a `PYTHONPATH` workaround because `build-pypi-package-action` wipes the
  environment and this repo's `tasks.py` imports itself. If `release.build` becomes callable without
  the project tasks (`python -m invoke_tasklib release.build`), the workaround and the `build-package`
  alias go away.

### 6.3 Test strategy

- `ci-test-deps.yaml` and `nightly-test-package*.yaml` test the oldest/newest `invoke` and import the
  published wheel, but never run a task. The fixture project of 3.1 gives them something real to run.
- The tools that tasks wrap (`ruff`, `ty`, `uv`, `mike`, `pyright`, `pytest`) are the main source of
  breakage for this library (a CLI flag changes), and only `dev` locks them. A nightly job that
  runs the fixture project against the _latest_ versions of the tools would find breakage before
  users do.

---

## 7. Suggested order of work

One logical change per PR, stacked where one depends on another (as the project's workflow asks).

1. **Make `main` green and honest** (no behavior change): fix the two failing doctests (1.1);
   correct `CLAUDE.md`; restore the admonition indentation and protect it (1.12); fix the README
   example (1.13); add `codespell` to `dev` and `warn=True` for `command -v python` (1.8).
2. **Robustness of `say` and the config** (small, high value): 1.2, 1.4, 1.5, with regression tests.
3. **Quoting everywhere** (1.3), then update `SECURITY.md`. Move the Markdown doctests to a single
   `python -m doctest` call in the same PR.
4. **The integration safety net** (3.1, 3.2, 3.3): the fixture project and its end-to-end tests, and
   the helper de-duplication. Do this _before_ the breaking changes so they are protected.
5. **Doctest engine and `check.all`** (1.1 second half, 2.4), enforce `W505` (1.14).
6. **Behavior fixes** one PR each: `clean` (1.6), program hints (1.7), `doc.publish-*` (1.9),
   `env.*` (1.10), test tasks (1.11), `--args` everywhere (2.2).
7. **Breaking changes in one release with a changelog and migration notes**: AST-based
   `imports.check-cycles` (2.1), `release.pypi` -> `release.publish` (2.3), declarative config and
   tuple groups (2.5), deprecating the shared `ns` (2.9).
8. **Docs and CI**: generated task tables, `strict` mkdocs, `doc.build` in CI, the reference pages,
   the custom-task page, `CHANGELOG.md` (section 4 and 6).

## What was and was not done

Run: the full unit suite with coverage, `ruff check`, `ruff format --check`, `ty check`,
`inv test.doctest`, `inv test.doctest-markdown`, `inv --list`, a build of the sdist and the wheel in
the scratchpad, `gh run list` (read only), and about twenty probes in a throw-away project outside the
repository (plus one `W505` run of ruff with the rule enabled) (the commands are quoted in the items marked **[verified]**).

Not done: the changes proposed here were not implemented, no test was added, and no branch or PR
was created. The items marked **[reading]** were not reproduced (in particular 1.9, 1.10, 2.1,
2.3 and 2.7), the `pip-audit`/`uv export` flags in 2.7 were not checked, and CI results could not be
read because every run is queued.
