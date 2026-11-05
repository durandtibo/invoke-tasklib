# Instructions for coding agents

## Environment

- Use the virtual environment in `.venv`: `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/ruff`.
  There is no `python` on the `PATH`.
- Lint and format before committing: `.venv/bin/ruff check src tests` and `.venv/bin/ruff format src tests`.
  Fix the issues raised by ruff. Ignoring an issue (`noqa`, a changed rule set) is not fixing it.
- Type check with `.venv/bin/ty check`. Fix the issues raised by ty. Ignoring an issue
  (`type: ignore`, `ty: ignore`, a cast that hides the problem) is not fixing it.
- Run the unit tests of the modules you changed (for example `.venv/bin/pytest tests/unit/test_lint.py -q`),
  then the whole suite (`.venv/bin/pytest tests -q`) and the doctests (`.venv/bin/inv test.doctest`).
  All the tests pass on `main`; if one fails, check with `git stash` before blaming your change.

## Workflow

- One branch and one pull request per logical change (one feature, one bug fix, one refactor).
  Branch from an up to date `main`.
- Name the branch `<type>/<short-description>` in lowercase kebab-case, for example
  `feat/add-cache-option` or `bugfix/handle-empty-input`. Use one of these types:
  `feat` (new feature), `bugfix` (bug fix), `hotfix` (urgent fix), `docs` (documentation),
  `refactor` (no behaviour change), `perf` (performance), `test` (tests only),
  `chore` (maintenance, dependencies, tooling), `ci` (CI configuration).
- Do not commit or push to `main`.
- When working on several sequential PRs where one depends on the previous one, use stacked PRs:
  branch each PR from the branch of the previous one (not from `main`) and open it with the
  previous branch as its base. Keep each PR small and reviewable on its own. Once a PR of the stack
  is merged, retarget the next PR to `main` and merge `origin/main` into it.
- In the PR description, say what was changed, what was deliberately not changed, and any
  behaviour change (for example a changed output, or a breaking change of the signature).
- When a PR conflicts with `main`, merge `origin/main` into the branch and resolve the conflicts
  (do not rebase and force-push). Most conflicts are two PRs appending tests at the end of the
  same test file: keep both. Check what `main` already contains before choosing a side.
- Update any tracking document (changelog, status table, issue) affected by the change, with the
  PR number.

## Code

- The source is in `src/invoke_tasklib/`: one module per task namespace (`formatting.py`,
  `lint.py`, `typecheck.py`, `testing.py`, `env.py`, `release.py`, `doc.py`, `security.py`,
  `imports.py`, `clean.py`, `check.py`, `fix.py`, `show.py`), plus `config/` (config
  resolution: `_schema.py`, `_validate.py`, `_derive.py`, `_constants.py`, `_resolve.py` with
  `get_config` and `load_config`, `__init__.py` that re-exports them, and `__main__.py` that
  prints the JSON schema), `runner.py` (the command runner), `tools.py` (tool lookup and install
  hints) and `output.py` (progress messages). Six private modules support the tasks: `_steps.py`
  (the step runner shared by `check.py` and `fix.py`: `run_composite` selects the steps,
  looks up their tools and runs them), `_files.py` (the file lookup of the format and
  test tasks), `_pyproject.py` (the reader of `pyproject.toml`), `_coverage.py` (where the
  coverage reports are written), `_graph.py` (the static import graph used by `imports.check-cycles`) and
  `_discover.py` (the module listing run in a subprocess by `imports.check-isolated`). The
  namespace of each module is its `NAMESPACE` constant, and the modules are registered in
  `_MODULES` of `src/invoke_tasklib/__init__.py`.
- Match the surrounding code: comment density, naming, docstring style (Google style with
  `Args:`, `Returns:`, `Raises:` and, where useful, an `Example usage:` with a `pycon` block that
  runs as a doctest).
- `inv test.doctest` runs every `>>>` example of every tracked markdown file, `review/` included. In a
  review (`review/*.md`), show an example that is not meant to pass (a bug that was fixed, a failing
  command) in a `text` block without the `>>>` prompt, not in a `pycon` block.
- Follow the current style of the repository in everything you add (source, tests, docs, commit
  messages, PR descriptions). Look at a few neighbouring files first, and do not introduce a new
  convention or reformat code you do not otherwise change.
- Read the config with `load_config(c)` (it exits with a message on an invalid config), never from
  `c.config` directly. Run external commands with `invoke_tasklib.runner.run` and build them with
  `build_command` (it quotes the arguments), and print progress with `invoke_tasklib.output.say`;
  do not call `c.run` or `print` in a task.
- Validate the `invoke.yaml` values in `config/_validate.py`, next to the existing `_validate_*` helpers.
- Keep new task options keyword-only where the signature allows it, and give each option a `help`
  entry in `@task`.
- Keep the read-only/mutating naming: `check_<target>` never modifies a file and `fix_<target>`
  does.
- Every function, public or private (leading underscore), needs a docstring and its own unit
  tests. Private functions are not exempt. Tasks are documented by their docstring: the first line
  is the one-line summary shown by `invoke --list`, so keep it to one sentence.
- Keep docstrings and documentation up to date and comprehensive: update them whenever the
  behaviour, signature or options of the code change. A new or changed task also updates the
  README task table, `docs/docs/uguide/index.md`, the page of the namespace in `docs/docs/uguide/`
  and `docs/docs/index.md`.
- Docstrings and comments are at most 72 characters wide, code at most 100 (`ruff` enforces it).

## Tests

- Always write tests for the code in `src/`, including every private function. Unit tests must be
  fast and efficient; tests that run the real tools (subprocess, files) go in
  `tests/integration/`.
- Unit tests mirror the source tree (`tests/unit/test_<module>.py`) and use
  `invoke.context.MockContext` to record the commands, with `make_context` and `commands` of
  `tests/helpers.py` (and, in the integration tests, `subprocess_context` of
  `tests/integration/helpers.py`). Do not call a real tool in a unit test.
- Do not use local imports inside tests. Import at the top of the module.
- One behaviour per test: a test has one `assert` or one `pytest.raises`. Split a test that checks
  several things into several tests. A `pytest.raises` may be followed by one `assert` on the
  caught exception (`info.value.code`), because the exception is the one behaviour. Do not add an
  `assert` on something else after it.
- Keep the unit tests simple and fast: no sleeps, no large data, no real network or heavy I/O,
  and no logic (loops, branches) in the test body.
- Add the missing tests to get 100% coverage of the code you add or change
  (`.venv/bin/pytest tests --cov=invoke_tasklib --cov-report=term-missing`). Do not use
  `# pragma: no cover` to skip a line that can be tested.
- Use `pytest.mark.parametrize` for the same check on several values.
- Every `pytest.raises` (and `pytest.warns`) must define `match` with a regular expression for the
  message (raw string if it has metacharacters), so a test does not pass on an unrelated error of
  the same type. An exception raised by a patched stand-in needs an explicit message for the same
  reason (`side_effect=KeyboardInterrupt("interrupted")`, not `side_effect=KeyboardInterrupt`).
- Add a regression test for every bug fixed, and check that it fails without the fix (revert the
  `src` change with `git stash push src` and run it).
- Do not add tests for the exports of `__all__` or other trivial structure.
- Section headers in the tests have three lines. The second line is `#`, 5 spaces, the name,
  5 spaces and `#`. The first and third lines repeat `#` to match the length of the second line:

  ```python
  ###########################
  #     Tests for Fixed     #
  ###########################
  ```

- Seed random data (`default_rng(0)`); no unseeded randomness in tests.
- Patching (`monkeypatch`, `unittest.mock.patch`) is fine in unit tests: it keeps them fast and
  simple and isolates the logic under test. But a patched test only proves the logic works against
  the patched stand-in, which may not match the real collaborator (signature, return type,
  behaviour). A passing patched unit test does not mean the feature works. Every patched behaviour
  needs an integration test in `tests/integration/` that exercises the real thing without patching.
  The two kinds of test have different purposes; do not drop one because the other exists.

### Test assertions

- When asserting an expected value, write the final computed value, not the expression that
  produces it. If the derivation is not obvious, keep the expression as a comment above the
  assertion.
- When a function returns a composite value (a dict, a list, ...), include at least one test that
  asserts the entire output against a fully-specified literal, not only individual keys or fields.
  For a task, assert the whole list of commands (`assert _commands(c) == [...]`).

### Test coverage

When implementing or modifying a function, write comprehensive unit tests, not just a happy-path
check. Cover, where applicable:

- Typical inputs.
- Edge cases: empty inputs, single-element inputs, duplicate inputs.
- Boundary values (0, negative numbers, min/max of a valid range).
- Error conditions: inputs that should raise, with the right exception type and message
  (including errors raised by collaborators the function calls).
- Interactions between parameters, for example a cross-product of two input lists, or the order
  of the commands.
- Side effects: the function does not mutate its inputs and is deterministic across repeated calls.

Prefer many small, precisely named tests (one behavior per test) over a few broad ones, so a
failure points at the specific behavior that broke.

## Reporting

- Report faithfully: say which tests were run, which were not, and that CI was not awaited.
- Mention test failures that already exist on `main` instead of hiding them.
