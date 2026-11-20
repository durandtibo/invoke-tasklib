# GitHub Actions workflows

This directory holds every workflow for the repository. There are no
subdirectories: GitHub only discovers workflows placed directly under
`workflows`, so reusable workflows live here too, alongside the top-level
ones that trigger on events.

## Naming convention

Every file is prefixed by what it does:

| Prefix      | Purpose                                                                                                                                                              |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ci-`       | Quality/test checks, most of them reusable workflows called from `workflows/ci.yaml`.                                                                                |
| `lib-`      | Reusable workflows with no event trigger of their own; they only expose `workflow_call` outputs (e.g. reading a JSON config file) and are `needs:`-ed by other jobs. |
| `bot-`      | Scheduled automation that pushes commits / opens PRs as the `ci-bot` GitHub App.                                                                                     |
| `nightly-`  | Scheduled checks against the _published_ PyPI package (as opposed to `ci-*`, which checks the repo's source).                                                        |
| `release-`  | Publishing: PyPI package, GitHub release assets, documentation.                                                                                                      |
| `security-` | Supply-chain/security scanning (Scorecard, dependency review, audit).                                                                                                |

`workflows/ci.yaml` is the entry point for pull requests/pushes to `main`; it
fans out to the `ci-*.yaml` reusable workflows so each check can also be
run/dispatched on its own. Job ids in `ci.yaml` and in the workflows it calls
are load-bearing for branch protection - keep them in sync if you rename
either side. Configure branch protection to require these status checks
(job name / called-workflow job id):

- `build / build`
- `format / format` and `format / shell`
- `check / check`
- `imports / imports`
- `lint / lint`
- `type-checking / type-checking`
- `pre-commit / pre-commit`
- `doctest / doctest` and `doctest / build`
- `test / all`
- `test-deps / test-dep`

Two `ci-*` workflows are deliberately _not_ called from `ci.yaml`, each
standalone with its own trigger instead: `ci-benchmark.yaml` runs nightly on
its own schedule rather than gating every PR/push, since a benchmark
regression isn't a merge blocker; `ci-verify-workflows.yaml` lints
`.github/workflows/*` itself, so it triggers on workflow-file changes rather
than every PR/push.

`nightly-repo-tasks.yaml` is the exception to the `nightly-` rule: it runs
`inv check.all --only shell,spelling` on the repo's source. The locked
dependencies are audited weekly by `security-audit.yaml`
(`inv security.audit`), since they change without any commit.

## Catalogue of the workflows

The trigger of a reusable workflow is `workflow_call`: it runs when another
workflow calls it (`ci.yaml` for the `ci-*` ones, `nightly-package.yaml` for
the `nightly-test-*` ones).

| Workflow                             | Trigger                                | Purpose                                                                         |
| ------------------------------------ | -------------------------------------- | ------------------------------------------------------------------------------- |
| `ci.yaml`                            | pull request, push to `main`, nightly  | Entry point: calls the `ci-*` checks below.                                     |
| `ci-build.yaml`                      | called by `ci.yaml`                    | Build the sdist and the wheel, and check that the built package installs.       |
| `ci-check.yaml`                      | called by `ci.yaml`, manual            | Run the composite `check.all` task (`inv check.all --keep-going`).              |
| `ci-doctest.yaml`                    | called by `ci.yaml`, manual            | Run the doctests (`inv test.doctest`) and check that the documentation builds.  |
| `ci-format.yaml`                     | called by `ci.yaml`, manual            | Check the formatting and the linting of the Python and shell files.             |
| `ci-imports.yaml`                    | called by `ci.yaml`, manual            | Check that there is no circular import and that the import contracts are kept.  |
| `ci-lint.yaml`                       | called by `ci.yaml`, manual            | Lint the Python files with ruff (`inv lint.check-python`).                      |
| `ci-pre-commit.yaml`                 | called by `ci.yaml`, manual            | Run all the pre-commit hooks.                                                   |
| `ci-test.yaml`                       | called by `ci.yaml`                    | Unit, integration and functional tests with coverage (`inv test.all --cov`).    |
| `ci-test-deps.yaml`                  | called by `ci.yaml`                    | One job per dependency, to test it with its supported versions.                 |
| `ci-test-code-dep.yaml`              | called by `ci-test-deps.yaml`          | Test the code with the supported versions of one dependency.                    |
| `ci-type-checking.yaml`              | called by `ci.yaml`, manual            | Type check the package (`inv types.check --complete`).                          |
| `ci-benchmark.yaml`                  | nightly, manual                        | Run the benchmarks and compare them with the previous run (not a merge gate).   |
| `ci-verify-workflows.yaml`           | pull request, push to `main`, manual   | Lint the files of `.github/workflows`.                                          |
| `lib-get-test-matrix.yaml`           | called by other workflows, manual      | Load the Python versions and the operating systems to test.                     |
| `lib-get-package-metadata.yaml`      | called by other workflows, manual      | Read the name, the version and the dependency specifiers from `pyproject.toml`. |
| `lib-get-package-versions.yaml`      | called by other workflows, manual      | Read the versions of the dependencies to test from `dev/config`.                |
| `nightly-package.yaml`               | nightly (10:30 UTC), manual            | Test the package published on PyPI: calls the `nightly-test-*` workflows.       |
| `nightly-test-package.yaml`          | called by `nightly-package.yaml`       | Run the checks against the installed PyPI package.                              |
| `nightly-test-package-dep.yaml`      | called by `nightly-package.yaml`       | Test the installed PyPI package with the supported versions of one dependency.  |
| `nightly-repo-tasks.yaml`            | nightly (10:40 UTC), manual            | Run the `shell` and `spelling` steps of `check.all` on the source.              |
| `release-pypi.yaml`                  | version tag `v*.*.*`, manual           | Run the CI, then build, sign and publish the package to PyPI.                   |
| `release-docs.yaml`                  | version tag `v*.*.*`, manual           | Deploy the documentation of the stable version (with `mike`).                   |
| `release-docs-dev.yaml`              | push to `main`, manual                 | Deploy the documentation of the development version.                            |
| `release-docs-publish.yaml`          | called by the two previous workflows   | Build and deploy the documentation (shared logic).                              |
| `security-audit.yaml`                | weekly (Monday), manual                | Audit the locked dependencies with pip-audit (`inv security.audit`).            |
| `security-dependency-review.yaml`    | pull request                           | Review the dependencies added by the pull request.                              |
| `security-scorecard.yaml`            | weekly, push, branch protection change | OSSF Scorecard supply-chain analysis.                                           |
| `bot-cancel-stale-queued-runs.yaml`  | hourly                                 | Cancel the runs that have been queued for too long.                             |
| `bot-format-files.yaml`              | weekly (Friday)                        | Format the YAML, Makefile, shell and Markdown files and open a pull request.    |
| `bot-generate-package-versions.yaml` | weekly (Thursday)                      | Update `dev/config/package_versions.json` and open a pull request.              |
| `bot-pin-action.yaml`                | weekly (Wednesday)                     | Pin the actions to a commit SHA (`ratchet`) and open a pull request.            |
| `bot-pre-commit-autoupdate.yaml`     | weekly (Tuesday)                       | Update the pre-commit hooks and open a pull request.                            |
| `bot-sync-shared-makefile.yaml`      | weekly (Wednesday)                     | Sync the shared Makefile subtree and open a pull request.                       |
| `bot-update-deps.yaml`               | weekly (Saturday)                      | Update the dependencies (`uv.lock`) and open a pull request.                    |

All the workflows can also be triggered manually (`workflow_dispatch`), except
the reusable ones that need inputs and the pull request security review.

## Composite actions vs. reusable workflows

- **`.github/actions/*`** (composite actions): used when the shared unit is a
  handful of _steps_ inside a single job (e.g. configuring git for `mike`,
  or verifying an installed package). Composite
  actions cannot produce a job-level output usable in a `strategy.matrix`.
- **`.github/workflows/lib-*.yaml`** (reusable workflows called with
  `uses: ./.github/workflows/lib-....yaml`): used when the output needs to
  feed a matrix, or when the shared logic is naturally a whole job (e.g.
  loading `durandtibo/workflow-config-action`'s config once and handing the
  JSON down to several jobs via `needs:`).

When adding new duplication, prefer extending an existing composite
action/reusable workflow over copy-pasting steps.

## Conventions applied to every workflow

- **Action pinning**: every third-party (and first-party `actions/*`) step is
  pinned to a full commit SHA with a trailing `# ratchet:owner/repo@vX.Y.Z`
  comment, meant to be added and refreshed automatically by
  [`ratchet`](https://github.com/sethvargo/ratchet) via `workflows/bot-pin-action.yaml`.
  Never hand-pin a SHA without that comment - the next `bot-pin-action` run
  would otherwise silently downgrade or drift it. Local composite actions
  (`uses: ./.github/actions/...`) are referenced by path, not pinned. Any
  runtime tool invoked outside of a pinned action (e.g. `npx <pkg>`) should
  also pin an explicit version, so a bot-authored PR can't pick up an
  unreviewed upstream release.
- **Permissions**: top-level `permissions:` is always the least the workflow
  needs - `contents: read` or `{}` - and any job that needs more (e.g.
  `contents: write` to push, `id-token: write` for OIDC) declares it on that
  job only, never widening the workflow default.
- **Timeouts**: every job sets `timeout-minutes`, sized to what the job
  actually does (2 for a config-read job, 5 for most checks, 10 for slower
  jobs like Scorecard, benchmarks, or the full test matrix) so a hung step
  can't occupy a runner indefinitely.
- **Runners**: `ubuntu-slim` for lightweight jobs that only run a small
  action or a couple of shell commands (no Python/build tooling); otherwise
  `ubuntu-latest`, or the OS matrix under test for `workflows/ci-test.yaml` /
  `nightly-test-package.yaml`.
- **`workflow_dispatch`**: added to every workflow (checks and automation
  alike) so it can be re-run manually without waiting for its normal trigger.

## Invoke tasks used by these workflows

CI/release steps call this repo's own `invoke_tasklib` tasks (via
`inv <task>`, in the virtual environment that
`durandtibo/setup-venv-uv-action` creates and activates) rather than
inlining raw tool commands, so the same checks a contributor runs locally
(`make`, `uv run inv --list`) are exactly what CI runs. The action installs
this repo in editable mode, since it is `invoke-tasklib` itself. Key mappings:

| Workflow job                | Invoke task                                                  |
| --------------------------- | ------------------------------------------------------------ |
| `ci-format.yaml` / `format` | `format.check-python`, `lint.check-python`                   |
| `ci-format.yaml` / `shell`  | `make check-format-shell`, `make lint-shell` (no task)       |
| `ci-check.yaml`             | `check.all --keep-going`                                     |
| `ci-lint.yaml`              | `lint.check-python`                                          |
| `ci-imports.yaml`           | `imports.check-cycles`, `lint-imports`                       |
| `security-audit.yaml`       | `security.audit`                                             |
| `ci-type-checking.yaml`     | `types.check --complete`                                     |
| `ci-doctest.yaml`           | `test.doctest`                                               |
| `ci-test.yaml`              | `test.all --cov`                                             |
| `ci-build.yaml`             | none (`durandtibo/verify-uv-build-action`)                   |
| `release-pypi.yaml`         | `build-package` (via `durandtibo/build-pypi-package-action`) |
| `release-docs-publish.yaml` | `doc.publish-latest`, `doc.publish-dev`                      |

`ci-pre-commit.yaml` runs `.pre-commit-config.yaml` directly via
`pre-commit/action` rather than an invoke task, since pre-commit already
orchestrates the hooks (including a `ty` hook that itself shells out to
`uv run inv types.check`).

Unlike upstream `durandtibo/coola`, this repo has no
`[project.optional-dependencies]` extras, so there are no `*-extras` job
variants or `lib-get-package-extras.yaml` / `lib-get-package-deps.yaml`
equivalents here. The `*-dep` variants (`ci-test-deps.yaml`,
`nightly-test-package-dep.yaml`) and `bot-generate-package-versions.yaml`
are scoped to invoke-tasklib's one runtime dependency, `invoke`, instead of
matrixing over extras.

## Shared configuration

Values that would otherwise be duplicated across workflows are centralized
instead of repeated:

- The supported Python versions / OS matrix is not in this directory: it is
  the default config of `durandtibo/workflow-config-action`, read once per
  run by `lib-get-test-matrix.yaml`.
- `../dev/config/package_versions.json` - tested `invoke` version list (its
  pyproject.toml lower bound through latest), read once per run by
  `lib-get-package-versions.yaml`. Regenerated weekly by
  `bot-generate-package-versions.yaml` via `../dev/generate_versions.py`.

The package name and version, and the version specifiers of the dependencies,
are never duplicated in config: they are read directly from
`../pyproject.toml` by the `durandtibo/extract-pyproject-metadata-action`
composite action, wrapped in `lib-get-package-metadata.yaml` so that its
outputs can be used by other jobs.

## Validating changes to this directory

`workflows/ci-verify-workflows.yaml` runs
`durandtibo/verify-github-workflow-action` on every PR/push that touches
`.github/workflows/*`, checking pinning and general workflow correctness.
Locally, `actionlint` (run from this directory) and a YAML syntax check are
good pre-flight checks before pushing:

```bash
cd .github/workflows && actionlint
python3 -c "import yaml, glob; [yaml.safe_load(open(f)) for f in glob.glob('*.yaml')]"
```
