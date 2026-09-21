# GitHub Actions workflows

This directory holds every workflow for the repository. There are no
subdirectories: GitHub only discovers workflows placed directly under
`workflows`, so reusable workflows live here too, alongside the top-level
ones that trigger on events.

## Naming convention

Every file is prefixed by what it does:

| Prefix      | Purpose                                                                                                                            |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `ci-`       | Quality/test checks, most of them reusable workflows called from `workflows/ci.yaml`.                                              |
| `lib-`      | Reusable workflows with no event trigger of their own; they only expose `workflow_call` outputs and are `needs:`-ed by other jobs. |
| `bot-`      | Scheduled automation that pushes commits / opens PRs as the `ci-bot` GitHub App.                                                   |
| `nightly-`  | Scheduled checks against the _published_ PyPI package (as opposed to `ci-*`, which checks the repo's source).                      |
| `release-`  | Publishing: PyPI package, GitHub release assets, documentation.                                                                    |
| `security-` | Supply-chain/security scanning (Scorecard, dependency review).                                                                     |

`workflows/ci.yaml` is the entry point for pull requests/pushes to `main`; it
fans out to the `ci-*.yaml` reusable workflows so each check can also be
run/dispatched on its own. Job ids in `ci.yaml` and in the workflows it calls
are load-bearing for branch protection - keep them in sync if you rename
either side. Configure branch protection to require these status checks
(job name / called-workflow job id):

- `build / build`
- `format / format` and `format / shell`
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

## Composite actions vs. reusable workflows

- **`.github/actions/*`** (composite actions): used when the shared unit is a
  handful of _steps_ inside a single job (e.g. `uv` setup + `uv sync`,
  configuring git for `mike`, or verifying an installed package). Composite
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
`uv run inv <task>`) rather than inlining raw tool commands, so the same
checks a contributor runs locally (`make`, `uv run inv --list`) are exactly
what CI runs. Key mappings:

| Workflow job                | Invoke task                                            |
| --------------------------- | ------------------------------------------------------ |
| `ci-format.yaml` / `format` | `format.check-python`, `format.check-docstrings`       |
| `ci-format.yaml` / `shell`  | `format.check-shell` (+ `shfmt -d`, no task wraps it)  |
| `ci-lint.yaml`              | `lint.check-lint`                                      |
| `ci-type-checking.yaml`     | `types.check`                                          |
| `ci-doctest.yaml`           | `test.doctest`                                         |
| `ci-test.yaml`              | `test.all --cov`                                       |
| `ci-build.yaml`             | `release.build --check`                                |
| `release-pypi.yaml`         | `build-package` (via `durandtibo/pypi-release-action`) |
| `release-docs-publish.yaml` | `doc.publish-latest`, `doc.publish-dev`                |

`ci-pre-commit.yaml` runs `.pre-commit-config.yaml` directly via
`pre-commit/action` rather than an invoke task, since pre-commit already
orchestrates the hooks (including a `pyright` hook that itself shells out to
`uv run inv types.check`).

Unlike upstream `durandtibo/coola`, this repo has no
`[project.optional-dependencies]` extras, so there are no `*-extras` job
variants or `lib-get-package-extras.yaml` / `lib-get-package-deps.yaml`
equivalents here. It does have a `*-dep` variant (`ci-test-deps.yaml`,
`nightly-test-package-dep.yaml`) and `bot-generate-package-versions.yaml`,
scoped to invoke-tasklib's one runtime dependency, `invoke`, instead of
matrixing over extras.

## Shared configuration

Values that would otherwise be duplicated across workflows are centralized in
`../dev/config`:

The Python-version/OS matrix is not one of these files: `lib-get-test-matrix.yaml`
loads it straight from `durandtibo/workflow-config-action`'s own built-in
default config (no local override), matching upstream `durandtibo/coola`.

- `../dev/config/package_versions.json` - tested `invoke` version list (its
  pyproject.toml lower bound through latest), read once per run by
  `lib-get-package-versions.yaml`. Regenerated weekly by
  `bot-generate-package-versions.yaml` via `../dev/generate_versions.py`.

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
