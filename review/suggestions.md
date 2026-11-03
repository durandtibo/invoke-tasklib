# Review of `invoke-tasklib` — suggestions

Scope: everything tracked in the repository — `src/` (12 modules), `tests/`, `tasks.py`, `dev/`,
`pyproject.toml`, `invoke.yaml`, `docs/` (all pages), `README.md`, `CONTRIBUTING.md`,
`CLAUDE.md`, `.pre-commit-config.yaml`, `.github/` (workflows and actions, skimmed for the
parts that interact with the library), and `Makefile`/`.make/` (glanced at only; it is a synced
shared makefile).

Baseline when reviewed (`main` at `3e8b209`): 61 unit tests pass, 100% line and branch coverage,
`ruff check` and `ty check` clean, doctests pass.

Breaking changes are allowed, so they are proposed where they give the better design. Each is
marked **[breaking]**. Items marked **[verified]** were reproduced in this checkout; the others
come from reading the code.

Suggested order of work is in the last section. Within a section, items are ranked by impact.

---

## 1. Bugs and correctness problems

### 1.1 `logger.info` messages are never shown **[verified]** — high

Every task reports progress through `logging.getLogger(__name__).info(...)` (the 🧹/📦/✅
messages). Invoke does not configure logging, so the root logger stays at `WARNING` and none of
these messages appear. Running `inv clean-pycache` prints nothing at all.

The progress and success messages are therefore dead code for every consumer who does not
configure logging themselves, and the library gives no way to do it.

Options, best first:

1. Stop using `logging` for user-facing progress. Print through the context
   (`c.config.run.out_stream`, or a small `say(c, msg)` helper) so output follows Invoke's
   `--hide`/`--echo` conventions and needs no logging setup.
2. Keep `logging`, and have `ns` install a handler on the `invoke_tasklib` logger the first time
   a task runs. Libraries configuring logging is generally discouraged, so (1) is preferable.

Related: emojis are hard-coded in every message. They break on terminals/CI log viewers with a
non-UTF-8 encoding, and they cannot be turned off. If (1) is done, add one switch (`tasklib.ui.emoji`
or an env var) in the same helper.

### 1.2 The bare `python` / tool invocations make tasks fail outside an activated venv **[verified]** — high

Tasks call `python -m pytest`, `python -m doctest`, `python -c`, `ruff`, `ty`, `pyright`,
`coverage`, `mike`, `docformatter`, `pre-commit` directly, but `security.audit` uses
`uv run pip-audit` and `release.build` uses `uv run --with`. In this checkout there is no
`python` on `PATH`; `inv test.benchmark` and `inv test.integration` fail with
`bash: python: command not found`. The project's own CI only works because the composite action
sets `activate-environment: true`.

Consequences: the invocation style is inconsistent between modules, a task can silently pick a
_different_ Python than the one `invoke` is running in, and `imports.check-cycles` can import the
wrong environment's copy of the package.

Proposal: introduce one internal helper (e.g. `invoke_tasklib.runner.run(c, cmd, **kw)`) and one
config key (`tasklib.runner.prefix`, default empty, typical value `uv run`) so that the command
prefix is decided in one place. For the Python-module tools use `sys.executable -m ...` instead of
`python -m ...` (the interpreter running Invoke is by definition the one that has the project
installed). This also gives one place to implement `echo`, `pty` and the logging from 1.1.

### 1.3 `release.build` does not verify the artifact it just built — high

```python
c.run(f'uv run --with {name} --refresh-package {name} --no-project -- python -c "import {name}"')
```

`--with <name>` asks uv to resolve the _name_ (from the index or the environment), not to install
`dist/*.whl`. The docs say "verifies the built wheel can actually be installed and imported"
(`docs/docs/uguide/release.md`), which this command does not guarantee. In this checkout the
command imported the module from `src/` (editable install), so it proved nothing about `dist/`.
Because the repo's `dist/` is stale (it still contains `0.0.2` artifacts), a mix-up is easy to
make.

Fix: install the wheel explicitly, e.g.
`uv run --isolated --no-project --with dist/<wheel> -- python -c "import <import_name>"`,
locating the wheel with `glob` in Python rather than in the shell. Do the same for the sdist
(build wheel from sdist is what PyPI users get).

### 1.4 `release.pypi` can publish stale artifacts and exposes the token on the command line — high

- `uv build` writes to `dist/` without clearing it, then `uv publish` uploads `dist/*`. A leftover
  `0.0.2` wheel next to a fresh `0.0.8` is uploaded too (it will be rejected by PyPI as an existing
  file at best). `uv build --clear` exists (checked with `uv build --help`); use it, or clean `dist/` first.
- `uv publish --token ${PYPI_TOKEN}` is expanded by the shell: an unset variable becomes an empty
  token and yields an obscure error, and the token appears in the process list. `uv publish` already reads
  `UV_PUBLISH_TOKEN` from the environment, so no `--token` is needed. Check the variable up front
  and fail with a clear message (`invoke.exceptions.Exit`).
- The repository's real release path is Trusted Publishing from `release-pypi.yaml`, which never
  calls `release.pypi`. The task is a second, weaker path that docs and troubleshooting still
  describe (`PYPI_TOKEN`). Either support `uv publish --trusted-publishing always` as the documented
  way, or deprecate/remove the task. **[breaking]** if removed.

### 1.5 `clean` walks into `.venv` and any other tree, and deletes inside it **[verified]** — high

`DIR_GLOBS = ("*.egg-info", "**/__pycache__")` with `Path().glob("**/__pycache__")` descends into
`.venv/` (one of the matches here is inside `.venv`), `node_modules/`, `.git/` and `site/`. It is
slow on large trees and mutates directories that the project does not own. `clean-pycache` has
the same behaviour. `test.doctest-markdown` already knows the exclusion list (`.venv`,
`.pytest_cache`, `.git`, `node_modules`) but `clean` does not share it.

Fix: share one `EXCLUDED_DIRS` constant (config-overridable) and walk with `os.walk`, pruning those
directories (or use `git ls-files --others --ignored --exclude-standard` as the source of truth).
Also clean `.mypy_cache`, `.ty_cache`/`.pytest_cache`-style caches consistently with what the
tools generate: today `.ruff_cache` is cleaned but a pyright/mypy/ty cache is not. Consider
`dist` being cleaned by `release.pypi` automatically (see 1.4).

### 1.6 `format.check-shell` / `fix-shell` run on vendored scripts **[verified]** — medium

`find . -name '*.sh' -type f -not -path './.git/*'` matches
`./.venv/lib/python3.12/site-packages/virtualenv/activation/bash/activate.sh`, so `shellcheck`
and, worse, `shfmt -w` (which rewrites files in place) run on third-party files inside the venv.
Exclude `.venv`, `node_modules`, `site`, `build`, `dist`, or use `git ls-files '*.sh'` which
respects `.gitignore` and is also faster. The docs only state that `.git/` is excluded.

### 1.7 YAML float coercion corrupts `python_version` **[verified]** — medium

`invoke.yaml` in this very repo writes `python_version: 3.14` unquoted. YAML parses `3.10` as the
float `3.1`, and `get_config` does `str(...)`, so a user asking for Python 3.10 gets
`uv venv --python 3.1`. The README and config docs quote the value, but nothing enforces it, and
this repo's own file does not.

Fix: validate the string with a regex (`^\d+\.\d+(\.\d+)?$`) and, when the raw value is a `float`,
raise a clear error ("quote the value: `\"3.10\"`"). Fix this repo's `invoke.yaml` too.

### 1.8 `groups` as a YAML list crashes **[verified]** — medium

`groups: {install: [dev, docs]}` is the natural YAML spelling, but `env.install` calls
`groups.split(",")` and raises `AttributeError: 'list' object has no attribute 'split'`.
Accept `str | list[str]` in config, normalise to a tuple in `get_config`, and keep the CLI flag
as a comma-separated string. (Invoke does support list-typed args, so
`--groups dev --groups docs` could be allowed via `iterable`, but that changes the CLI.)

### 1.9 Unknown config keys are silently ignored **[verified]** — medium

`paths: {unit_test: x}` (typo) is accepted and the default is silently used. A user debugging
"my custom path isn't picked up" (the troubleshooting page has a section on exactly this) has no
signal. Validate the keys of `package`, `paths`, `groups` against the TypedDicts and raise a
`ValueError` listing the unknown keys and the closest valid one (`difflib.get_close_matches`).

### 1.10 `doc.publish-latest` can publish the wrong thing — medium

- With no tag it logs a warning and publishes the docs as version `0.0` with the `latest` alias
  and sets it as the default. For a release task, "no tag" is a setup error; fail instead.
- A pre-release tag (`1.2.0rc1`) is truncated to `1.2` and becomes `latest`. Skip pre-releases
  (`Version.is_prerelease`) or require an explicit flag.
- `mike delete` before `mike deploy` is redundant (`deploy` replaces an existing version) and
  leaves the site without that version if the second command fails. Drop the delete.
- It needs `packaging`, which is not declared anywhere (not in `[dependency-groups]`; it only
  arrives transitively through `feu[all]`). Both the docs and troubleshooting tell users that
  `--groups dev,docs` installs it, which is not true for a project that does not depend on `feu`
  transitively. Either declare it, or parse the tag without `packaging`, or take the version from
  an explicit argument (`doc.publish-latest --version 1.2`) so that no tag lookup and no `feu` are needed.

### 1.11 `imports.check-cycles` checks less than it claims — medium

- Only packages (`ispkg`) are imported, not modules. A cycle between two sibling modules is only
  found if one of them happens to be imported first by a package `__init__`. For a flat package
  like this one (12 modules, one package) the task effectively runs `import invoke_tasklib` twice.
  Import every module (`walk_packages` without the `ispkg` filter), each in a fresh interpreter,
  or better use one subprocess per module only for modules and a single one for the discovery.
- `pkgutil.walk_packages` imports every package while walking, so the discovery step itself can
  fail with the cycle error it is meant to detect, with a traceback instead of the report. Use
  `pkgutil.iter_modules` on `importlib.util.find_spec(name).submodule_search_locations` recursively
  (no import), or walk the source directory.
- The discovery program is a string embedded in the task and re-embedded verbatim in the test
  (`tests/unit/test_imports.py` repeats the shell-quoted script). Move the script to a real
  module (`python -m invoke_tasklib._discover <name>`) or do the discovery in-process with
  `importlib.metadata`/`find_spec`; the test then no longer needs to mirror the quoting.
- `package.name` is used as an import name here but also as a distribution name in
  `release.build` and as a folder name for `paths.src`. See 2.3.

### 1.12 Smaller correctness issues — low

- `env.create-venv` runs `uv tool install invoke`, which installs `invoke` as an isolated _tool_
  (on `PATH` via `~/.local/bin`), not into the `.venv` just created. The docstring and
  `docs/uguide/env.md` ("installs `invoke` into it") are wrong. Either run `uv pip install invoke`
  after creating the venv, or reword; also state that the task needs `invoke` to already exist
  (chicken-and-egg: you run it with `invoke`).
- `env.install` runs `uv sync --frozen` and then `uv pip install -e .`. `uv sync` already installs
  the project in editable mode, so the second command is redundant; it can also undo the exact
  sync (it may add or change packages outside the lockfile). Check whether it is still needed.
  Both `uv sync --frozen` calls use `--frozen`, which does not verify that the lockfile is up to
  date; `--locked` fails when it is stale and is usually what CI wants.
- `env.update` runs `uv sync --upgrade` (default groups), then `install()` re-syncs with
  `--frozen` and different groups. The first sync is wasted work and the order of lock/sync is
  confusing. Prefer `uv lock --upgrade` followed by one `install`.
- `env.show-python-config` uses `which python`; use `command -v python` or Python's `shutil.which`
  (also works if the shell is not POSIX), and `uv python find` already covers most of it.
- `test.all` uses `--timeout 10` for the whole `tests/` tree, including `tests/integration` and
  `tests/functional`, which `test.integration` and `test.functional` deliberately give 60 s. Running
  `test.all` therefore applies the _unit_ timeout to slow tests. Give `test.all` the larger value,
  or run the three scopes with their own timeouts in sequence (and document the behaviour).
- `test.benchmark` needs `pytest-benchmark`, which is not a dev dependency of this project;
  `.github/workflows/ci-benchmark.yaml` runs it nightly. There is no `tests/benchmarks` here, so the
  nightly job can only fail (pytest exits non-zero on a missing path). Same for `test.integration`
  and `test.functional` in this repo. Either add a trivial benchmark/integration test (see 4.1),
  or make the task skip with a message when the directory does not exist.
- `lint.check-python` always passes `--output-format=github`. Run locally it prints raw
  `::error file=...` workflow commands that are unreadable. Make it an option
  (`--output-format`, default `None`, with `GITHUB_ACTIONS` auto-detection).
- `format.*` and `lint.*` run on `.` while `format.*-docstrings` runs on `paths.src`, so what is
  covered depends on the task. Decide on one rule and expose it in config (`paths.format: [src, tests, ...]`).
  The repo's own CLAUDE.md asks to run `ruff` on `src tests` only.
- `release.build` checks that `import <name>` works, but `package.name` is also the folder name
  in `src/<name>`; a distribution whose pip name differs from its import name (`pyyaml`/`yaml`,
  `invoke-tasklib`/`invoke_tasklib`) needs two keys. See 2.3.
- `types.check` is hard-wired to `ty check` with no paths. Allow `paths`/extra args (see 2.1).

---

## 2. Design and API improvements

### 2.1 Let users pass arguments through to the underlying tool — high **[breaking]-free**

None of the test/format/lint/type tasks can receive additional arguments. The most common needs
are `-k expr`, `-x`, `-m marker`, `--lf`, a single file, `-n auto`. Today a user must drop to
`pytest` directly, which defeats the "single entry point" goal. Add a uniform option, e.g.
`--args "-k foo -x"` (parsed with `shlex.split`), or a variadic positional through
`invoke --  args`. A shared helper builds the command so all tasks behave alike.

Also allow `--paths` on `format.*`, `lint.*`, `types.check`, `test.unit` to restrict a run to a
file (this is what `pre-commit` and editor integrations want).

### 2.2 Deduplicate the four test tasks — medium

`test.all`, `test.unit`, `test.integration`, `test.functional` are the same function with different
`(path, timeout, append)` triples and four hand-copied coverage blocks. Build them from a single
`_run_pytest(c, path, *, timeout, cov, append)` helper (and test the helper once, with the four tasks
as thin wrappers). Expose the timeouts in config (`tasklib.test.timeout.unit/integration/functional`),
since 10 s and 60 s are hard-coded, and a project with a slower suite cannot change them.
Also decide whether `--xdoctest` should be unconditional: it requires `xdoctest`, which is not
listed in the required tools table of `uguide/index.md`; a project without it gets
`unrecognized arguments: --xdoctest`. Make it a config switch (`tasklib.test.xdoctest: true`) or
detect it.

Coverage handling has two further gaps: `--cov` does not use `--cov-fail-under` (a threshold
belongs in the project config, but the task could forward it), and `unit --cov` does not erase
previous data while the other two `--cov-append`, so the result of `unit --cov; integration --cov`
depends on what was run before. Run `coverage erase` explicitly in `test.all --cov`, or add `--cov-reset`.

### 2.3 Separate the distribution name from the import name — medium **[breaking]**

`package.name` is used as: import name (`imports`, `release`, `test --cov=`), distribution name
(`uv run --with`), and the default directory (`src/<name>`). That only works when all three are
identical. Introduce `package.import_name` (default: `name` with `-` replaced by `_`) and keep
`package.name` as the distribution name. This is breaking only for the edge cases; for everyone
else the defaults keep today's behaviour. Same for flat layouts: `paths.src` defaults to
`src/<name>`, so a flat package needs an explicit override; detecting `src/<import_name>` then
`<import_name>` would remove the need.

### 2.4 Make `ns` a factory, not a shared mutable singleton — medium **[breaking]**

`ns` is a module-level `Collection`. This repo's own `tasks.py` does `ns.add_task(build_package)`,
which mutates the object shared by every importer in the process. Provide `make_ns(*, exclude=(),
include=None)` (and keep `ns = make_ns()` for compatibility if wanted) so that a project can:
drop tasks it does not use (`release.pypi`, `doc.*` — currently every consumer gets all 30 tasks,
including mutating ones that publish to PyPI), and add its own without side effects. Document it
in the README next to "Composing a custom subset of tasks".

Also, `clean.all` and `clean.pycache` are plain functions (not `@task`), wrapped by hand in
`__init__.py`. So `Collection(clean)` — which the docstring and README suggest as the way to
compose modules — yields an empty collection, unlike every other module. Make them `@task`s
named `clean`/`clean-pycache` (Invoke supports `name=` and `default=True`) and add the module as
`Collection.from_module(clean)` like the others. Naming a function `all` (here and in `test.py`)
shadows the builtin and needs `noqa: A001`; `@task(name="all")` on `def all_()` avoids that.

### 2.5 Fail with friendly errors instead of tracebacks — medium

Missing `package.name` raises `ValueError` which Invoke prints as a Python traceback. For a CLI,
use `invoke.exceptions.Exit(message, code=2)` (or `ParseError`) from tasks; keep `ValueError` in
`get_config` for programmatic use and convert in a small decorator or in `run`. The same
applies to missing external tools: check `shutil.which("ruff")` before running and say which
`env.install --groups ...` fixes it (the troubleshooting page is a whole section about this
failure mode, which the library could just diagnose).

### 2.6 Show what is being run — medium

`c.run` is called without `echo=True`, so the user cannot see the command line (and with
`pty=True`, they see the tool's output only). Pass `echo=True` by default (Invoke's `-e` already
turns it on globally, so respect `c.config.run.echo` instead of forcing it). Combined with 1.1 and 1.2
this is one change in the shared helper.

`pty=True` is hard-coded everywhere: it fails on Windows (the package does not claim support, but
there is no explicit guard), merges stderr into stdout, and breaks in some CI sandboxes. Make it
`pty=sys.stdout.isatty()`/config-driven in the helper.

### 2.7 Task help is truncated in `invoke --list` **[verified]** — medium

`docformatter` (wrap-summaries = 72) breaks summary lines, and Invoke shows only the first line
in `--list`:

```text
  clean                         Remove build artifacts and caches (dist,
                                __pycache__,
  security.audit                Audit installed dependencies for known
                                vulnerabilities with pip-
  test.coverage-report          Generate an HTML coverage report from the last
                                recorded coverage
  imports.check-cycles          Check for cyclic import dependencies by
                                importing each subpackage
```

(`pip-\naudit` is a hyphen split mid-word.) Rewrite the summaries of `clean.all`, `env.update`,
`format.check-docstrings`, `imports.check-cycles`, `security.audit`, `test.coverage-report` so that
each is a single line shorter than 72 characters, with the detail in the body. Note that the
long-line docformatter wrap is also what produced the odd
`inv build-\npackage` text in `tasks.py`. A unit test that asserts every task's first docstring
line is a complete single line (`len(task.help_text...)`/`"\n" not in summary`) prevents regressions.
Add `help={...}` for options (only `types.check` has it); `inv --help test.unit` currently
shows `c: The invoke context.` as if it were an option description.

### 2.8 Missing tasks that the repo itself already needs — low

The repo's pre-commit and `Makefile` run `codespell`, `markdownlint`/`prettier`, `yamllint`,
`checkmake`, `taplo`; the tasks only cover the Python and shell parts. For a library whose pitch is
"one consistent set of commands", consider `lint.check-spelling` (codespell), a `check`
composite (`format.check-* lint.check-* types.check imports.check-cycles test.unit`, what
`uguide/index.md` tells people to chain by hand), and `docs.build`/`docs.serve` (`mkdocs build --strict`).
In particular the CI "docs build" step runs `mike deploy` into a throw-away branch, which does
not use `--strict` and so does not fail on broken links or missing references; `mkdocs build
--strict` is the right check and is cheaper.
Wrapping `pre-commit run --all-files` as `lint.pre-commit` is another candidate.

### 2.9 Module names shadow the standard library — low **[breaking]**

`invoke_tasklib.types`, `invoke_tasklib.test`, `invoke_tasklib.format` (`noqa: A004`) share names
with `types`, the `test` package, and the `format` builtin. It works through absolute imports, but
it forces the `from ... import format  # noqa: A004` and the odd `test as test_tasks` alias in tests,
and `types.py` in a directory on `sys.path` is a classic source of confusing import errors
(for instance running a script from `src/invoke_tasklib/`). Since the namespace name is given by
`Collection(name=...)`, the modules can be renamed (`tasks_types`, `tasks_test`, ...) without changing the
task names. If renaming is too disruptive, at least stop doing `Collection.from_module` on them by
module name and pass the name explicitly (already done), and document why.

### 2.10 Configuration schema niceties — low

- `get_config` returns plain dicts built through `TypedDict` constructors; a frozen
  `dataclass` (or `NamedTuple`) gives attribute access (`cfg.paths.src`), `__post_init__`
  validation and a natural place for 1.7–1.9. **[breaking]** for anyone using `cfg["paths"]["src"]`
  in a custom task (the docs recommend exactly that).
- `DEFAULT_PACKAGE`/`DEFAULT_PATHS` are typed `dict[str, str | None]` and then filled lazily in
  `get_config` (`if not paths["src"]: ...`). A path set to `""` is treated like "unset". Using
  `None` checks (`is None`) is more predictable; and defaults derived from other keys can be
  `Callable` fields in one table instead of five `if` statements.
- `get_config` is re-evaluated by every task, and `install` -> `update` calls it twice. Fine
  performance-wise (the architecture doc says so) but it makes the validation errors fire late,
  in the middle of a task. Validate once when the collection is loaded (`Collection.configure`).
- Add `tasklib.paths.docs_config` existence checking only where it is used, with a clear message.

---

## 3. Documentation

Verified against the code; these are factual problems, not style.

| Where                                                          | Problem                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `README.md`, `docs/docs/uguide/index.md`, `docs/docs/index.md` | The task tables and feature lists omit `clean-pycache` (README and guide), `types.check --complete` (pyright mode, not mentioned in README, `uguide/types.md`, or `index.md`), and the `groups` config keys (README "Configuration" block lacks `groups`; `config.md` has it). `docs/docs/index.md` has no Security or Clean section at all.                                                                                                                                                                                                                                                     |
| `docs/docs/get_started.md`                                     | The sample `invoke --list` output is stale: it lacks `security.audit`, `imports.check-cycles`, `test.coverage-report`, `clean` and `clean-pycache`, has a misaligned `lint.check-python` line, and shows full-sentence descriptions where the real output wraps and truncates (see 2.7). Generate it from `inv --list` in CI or a doctest instead of hand-writing it.                                                                                                                                                                                                                            |
| `docs/docs/dev/architecture.md`                                | Says every task module is "a flat collection of `@task`-decorated functions" (not `clean`); shows `TasklibConfig` without `groups`; lists defaults as `DEFAULT_PACKAGE`/`DEFAULT_PATHS` (also `DEFAULT_GROUPS`); module list omits `imports.py`, `security.py`, `clean.py`; claims "Raises ValueError if package.name is missing" (true) but says validation is in one place (it is also in 1.7–1.9 above, not validated). The "Future Directions" item (`--config-schema`) is the right idea and is covered by 1.9.                                                                             |
| `docs/docs/dev/development.md`                                 | "Project Structure" and "Adding a New Task" list only 7 of the 10 task modules; the test example asserts on `c.run.call_args` which is not a public way to inspect `MockContext` (the tests use a `_commands` helper that asserts `isinstance(run, Mock)`). Document the helper (and move it to `conftest.py`, see 4.2).                                                                                                                                                                                                                                                                         |
| `docs/docs/uguide/env.md`                                      | "installs `invoke` into it via `uv tool install`" is wrong (see 1.12).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `docs/docs/uguide/release.md`                                  | "verifies the built wheel can actually be installed and imported" overstates (see 1.3). Mentions `PYPI_TOKEN` as the only mechanism while the repo's own release uses Trusted Publishing.                                                                                                                                                                                                                                                                                                                                                                                                        |
| `docs/docs/uguide/format.md`                                   | Says shell tasks exclude only `.git/` (and see 1.6).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `docs/docs/uguide/test.md`                                     | Says `test.doctest-markdown` skips `.venv`, `.pytest_cache`, `.git`, `node_modules`; `site/`, `build/`, `dist/`, `.tox`, `.mypy_cache` are not skipped, so generated HTML/markdown copies are doctested. `rglob("*.md")` also traverses `.venv` before filtering, which is slow; `git ls-files '*.md'` avoids both. It also starts one interpreter per file; one `python -m doctest f1 f2 ...` invocation (doctest accepts several files) is faster and reports all failures at once.                                                                                                            |
| `docs/docs/troubleshooting.md`                                 | "`--groups dev,docs` additionally installs mike, feu, packaging": `packaging` is not declared (1.10). The `invoke: command not found` advice says `env.create-venv` installs invoke as a tool (see 1.12).                                                                                                                                                                                                                                                                                                                                                                                        |
| `CLAUDE.md`                                                    | Largely copied from another project (`coola`): it refers to `coola.utils`, `coola.validation`, `LazySingleton`, `hash_object`, `numpy/torch/pandas/polars` lazy imports, `tests/integration/helpers.py` with `run_threads`, and the command example `pytest tests/unit/hashing`. None of these exist here. This is a real risk: an agent following it will look for modules that do not exist or invent them. Rewrite it for this repository (valid paths, `inv` tasks, no `coola` references). It also says "Run the unit tests... Some tests fail on `main`" which is not true here (61 pass). |
| `CONTRIBUTING.md`                                              | The code-style section says "Maximum line length: 100 characters" but does not mention the 72-character limit for docstrings/comments (`max-doc-length = 72`), which is what `ruff` actually enforces on them.                                                                                                                                                                                                                                                                                                                                                                                   |
| `README.md` / `pyproject.toml`                                 | The classifiers only list Linux and macOS (consistent with `pty=True` and `which`), but the README never says Windows is unsupported. State it.                                                                                                                                                                                                                                                                                                                                                                                                                                                  |

Other documentation suggestions:

- Generate the task tables (README, `uguide/index.md`, `get_started.md`) from the collection
  (`ns.task_names`/docstrings) in `dev/`, and check them in CI, so they cannot drift (they have:
  see above). `dev/generate_versions.py` is a precedent for generated files.
- `mkdocs.yml`: add `strict: true`; `validation:` block for broken links; `edit_uri`; the nav lists
  the 11 reference pages that each contain one line (`::: invoke_tasklib.<mod>`), fine, but
  `refs/*.md` could be generated by `mkdocs-gen-files` to avoid forgetting one when a module is added
  (the `config` -> `groups` omission is the same class of drift).
- Show a real end-to-end example in the README: a consumer's `pyproject.toml` dependency groups
  (`dev`, `docs`) that the default tasks assume, and the exact tools they must contain. Today the
  required-tools table is on page 4 of the guide, but `env.install` silently assumes groups called
  `dev` and `docs` exist; a project without a `docs` group fails in `env.update` with a uv error.
- Add a CHANGELOG (the project links GitHub releases) and a **migration note for each breaking
  change** adopted from this review. `CLAUDE.md` mandates updating the changelog but there is none.

---

## 4. Tests

The tests are tidy and complete for what they check (100% coverage), but coverage hides one
structural limit: every test uses `MockContext`, so no test ever runs a real command or a real
`invoke` process. The repo's own `CLAUDE.md` demands an integration test for every patched
behaviour, and there is no `tests/integration/` at all. Findings:

### 4.1 Add integration tests — high

Candidates, all cheap and without network access:

- Run `invoke --list` against this repo's `tasks.py` in a subprocess and assert the exact set of
  task names (catches a task that is defined but never registered, and 2.7).
- `inv clean` in a `tmp_path` project: create the directories, run, assert they are gone, and that
  `.venv/**/__pycache__` is untouched (regression for 1.5).
- `imports.check-cycles` against a tiny generated package with a deliberate cycle (and one without).
  This is the only task with real logic besides `get_config`, and the unit test only compares a
  quoted string.
- `release.build` against a generated minimal project (needs `uv`; mark/skipif when it is not
  installed), asserting the artifact in `dist/` is what was verified (regression for 1.3).
- `format.check-shell` on a `tmp_path` containing a `.venv/x.sh` (regression for 1.6).
- `test.unit` in a temp project that has one trivial test, so the pytest flags
  (`--xdoctest --timeout`) are exercised against the real plugins. Today a typo in the flag string
  would pass all 61 tests.

### 4.2 Remove the duplicated helpers — medium

`_context(...)` is copy-pasted in 11 test files and `_commands(...)` in 9 (identical bodies). Move them to
`tests/conftest.py` as fixtures (`make_context`, `commands`) or to `tests/helpers.py`. A fixture
`ctx` with a `ctx.commands` accessor (a small `MockContext` subclass or wrapper) also removes the
`assert isinstance(run, Mock)` boilerplate that exists only to satisfy the type checker.

### 4.3 Align with the project's own testing rules — medium

`CLAUDE.md` / `CONTRIBUTING.md` set rules that the existing tests do not follow:

- "A test has one assert": `test_get_config_overrides` asserts four things; `test_doctest_markdown`
  variants are fine, but several `test_*` split poorly by behaviour. Split by behaviour.
- `test_all_no_artifacts` in `test_clean.py` has no assertion at all (it passes if nothing raises);
  assert that `shutil.rmtree` and `Path.unlink` were never called.
- Private functions need their own tests: `clean._remove_dir` and `clean._remove_file` are only
  exercised through `clean.all`/`clean.pycache`; `format._FIND_SH` and `test.MARKDOWN_DOCTEST_EXCLUDE_DIRS`
  are only checked indirectly.
- "Do not add tests for trivial structure" is respected, but `test_init.py` asserts the set of
  sub-collections and `clean` only; it does not assert task names, so a renamed or missing task
  (e.g. `clean-pycache`, `build-package`) goes unnoticed. A single test comparing `ns.task_names`
  with a literal is a better regression guard for the public API (the repo's rule asks for
  whole-output literals).
- Section headers (`#####` banners) and `pytest.raises` with `match` are mixed: `match` is used, banners
  are not; either adopt the banner convention for the long files (`test_test.py`: 186 lines) or drop it
  from the rules.
- `test_clean.py` monkeypatches `Path.is_dir`, `Path.is_file`, `Path.glob`, `shutil.rmtree` and
  `Path.unlink` with lambdas. Real filesystem tests with `tmp_path` + `monkeypatch.chdir` are
  shorter, faster to read, and test the real behaviour (they would have caught 1.5). Same applies
  to `test_doc.py`, which hand-builds fake `sys.modules["feu"]` entries: `feu` is a dev dependency,
  so use the real module, or `pytest.importorskip`, and patch only `get_last_version_tag_name`.
- `test_init.py` and `test_doc.py` have imports after an `if TYPE_CHECKING:` block
  (`test_doc.py` imports `invoke_tasklib.doc` _after_ the guard). Ruff's isort did not flag it, but it
  breaks the layout used in every other file.

### 4.4 Cases that are not tested — medium

- Error paths: `c.run` raising `UnexpectedExit` (the tasks do not catch it; fine, but no test shows
  that the non-zero exit propagates, which is the whole contract of the `check_*` tasks).
- `get_config` with `package.name` of the wrong type (int, list), `paths.src: ""`, `python_version`
  as float (1.7), `groups` as list (1.8), unknown keys (1.9), `tests: ""`.
- `env.install` with `groups=" , "` (all-blank entries) and with duplicate groups
  (`"dev,dev"` produces `--group dev --group dev`).
- `test.coverage_report` and `types.check` are only tested with defaults; `doctest_markdown`
  paths containing spaces are passed unquoted to `c.run` (`f"... {f}"`), so a file called
  `my notes.md` becomes two arguments. Quote with `shlex.quote` and add the test. The same applies to
  `docs_config`, `src`, `name`, `tests`, `benchmarks`, `groups` interpolated into command strings throughout
  `doc.py`, `env.py`, `format.py`, `release.py`, `test.py`: a config value with a space or a shell metacharacter
  breaks or alters the command (`paths.src: "src/my pkg"`). Quoting at one place (the helper from 1.2)
  fixes it for all tasks; `imports.py` already does it with `shlex.quote`, the others do not.
- Doctests: the only doctest in `src` is in `__init__.py` and `config.py`; the project rule asks for a
  runnable `pycon` example per function. Task functions are thin, but `get_config`-like helpers
  (`clean._remove_dir`, the future command-builder helpers) should have them.

### 4.5 CI / tooling observations — low

- `ci-test.yaml` is called "Unit & Integration Tests" and the comment says "runs unit, integration
  and functional tests", but only `tests/unit` exists. Either add the integration tests (4.1) or fix the
  wording.
- `setup-uv-env` runs `uv sync --group dev` (neither `--locked` nor `--frozen`) so a stale `uv.lock`
  is silently re-resolved in CI, then `uv pip install -e .`, redundant per 1.12. Use `uv sync --locked`.
  The `uv-lock` pre-commit hook covers local commits only.
- Two different `astral-sh/setup-uv` pins exist (`bec219d…` v10.1.0 in `setup-uv-env`, `68559e9…`
  v10.3.3 in `release-pypi.yaml`). The `bot-pin-action` workflow exists to keep pins aligned; check why they differ.
- `ci-test-deps.yaml` and `dev/config/package_versions.json` test only the `invoke` lower/upper
  bounds `["3.0.0", "3.0.3"]`; fine for one dependency. Not covered: the optional tools the
  tasks shell out to (`ruff`, `uv`, `mike`, `feu`); a smoke test that runs each task's command
  `--help` in CI (e.g. `uv run ruff --version`) would catch an upstream CLI change (the repo already has a
  nightly job pattern for this).
- `pyproject.toml`: `lint.fixable` repeats the whole `lint.select` list (it is the default, `["ALL"]`
  is enough); `ruff` `lint.select` includes `T20` (no prints) while 1.1 suggests printing: use the
  context stream, which stays compatible.
- `[tool.ty.src] include = ["src", "tests", "dev"]` but `[tool.pyright] include = ["src"]`: the two
  type checkers in `types.check --complete` check different trees; align them or document why.
- `dev/generate_versions.py` module docstring says "Adapted from coola's dev/generate_versions.py"
  and wraps `dev-dependencies` words mid-hyphen (`dependency- compatibility`,
  `nightly-test-\npackage-dep.yaml`) for the same docformatter reason as 2.7; `dev/` is not covered by `check-docstrings`
  (it only runs on `paths.src`), so it was wrapped once and then left. Fix the text.

---

## 5. Suggested order of work (one PR each, small and reviewable)

1. **Fix verified bugs, no API change**: 1.5 (`clean` excludes), 1.6 (shell excludes), 1.7 (python version
   validation, quote this repo's `invoke.yaml`), 1.8 (list groups), 1.9 (unknown keys),
   1.3/1.4 (release verification, `--clear`, token), 4.4 quoting. Each with a regression test that fails
   without the fix.
2. **Shared command runner** (1.2 + 1.1 + 2.6 + quoting): one internal helper, then migrate the modules one
   at a time. This unblocks 2.1 (extra args) and 2.2 (test tasks dedup).
3. **Docs correctness** (section 3), including rewriting `CLAUDE.md`, plus the one-line help
   summaries (2.7) with the regression test.
4. **Integration tests** (4.1) and test helper cleanup (4.2/4.3) — before the breaking changes so that
   they protect them.
5. **Breaking changes, grouped in one release with a migration note**: `make_ns` factory and `@task`
   clean (2.4), `import_name` split (2.3), dataclass config (2.10), module renames (2.9), removing or
   replacing `release.pypi` (1.4).
6. **Nice to have**: new tasks (2.8), generated tables and `mkdocs --strict` (section 3), CI hygiene (4.5).

Nothing in this review was changed in the code: the only file written is this one. No tests were
added or run beyond the baseline listed at the top and the commands used to verify the items marked
**[verified]**.
