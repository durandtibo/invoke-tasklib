# Clean

:book: This page describes the `invoke_tasklib.clean` module.

## Overview

| Task            | Behavior                                              |
| --------------- | ----------------------------------------------------- |
| `clean.all`     | Removes build artifacts and caches from the repo root |
| `clean.pycache` | Removes all `__pycache__` directories                 |

`clean.all` is the default task of the `clean` namespace, so `invoke clean` runs it.

## Usage

```shell
invoke clean
```

Removes, if present, at the repository root:

- Directories: `build`, `dist`, `.pytest_cache`, `.ruff_cache`, `.coverage_html`, `htmlcov`,
  `.benchmarks`, `.mypy_cache`, `.tox`, `.nox`, `.hypothesis`, the HTML coverage directory if `[tool.coverage.html] directory` of `pyproject.toml`
  sets another one, and the MkDocs output
  directory, only if the MkDocs config file exists (what produces it): the `site_dir` of
  `paths.docs_config`, relative to the config file (`docs/site` by default). If the config is not
  valid, `site` for a `mkdocs.yml` and `docs/site` for a `docs/mkdocs.yml` are used
- Glob-matched directories: `*.egg-info` (at the root and in `src`) and every `__pycache__`
  directory of the project. The `.venv`, `.git`, `.pytest_cache` and `node_modules` directories are never walked
  into, so nothing inside them is removed.
- Files: `.coverage`, `.coverage.*` (parallel coverage data), `coverage.xml`

A top-level directory that contains files tracked by git (for example a `build/` directory with
scripts that are committed) is kept, and the task says so (`⏭️  Keeping build: it contains files
tracked by git`). Outside a git repository, or without `git`, nothing counts as tracked. The caches
(`__pycache__`, `*.egg-info`) and the files are not looked up.

A directory outside the project is never removed: if the `site_dir` of the MkDocs config is an
absolute path, contains `..` or points to the project root, the task says `⏭️  Not removing ...: it is
outside the project` and goes on.

Nothing is removed if the corresponding directory or file doesn't exist, so `clean` is safe to run
repeatedly (it's idempotent) and doesn't fail on an already-clean checkout. A symbolic link to a
directory is removed as a link, and the directory it points to is left untouched.

To see what would be removed without removing anything, add `--dry-run` (to `clean.all` or
`clean.pycache`):

```shell
invoke clean --dry-run
```

It prints a `Would remove <path>` line per path instead of `Removing <path>`.

To remove only the `__pycache__` directories:

```shell
invoke clean.pycache
```

## See Also

- [`invoke_tasklib.clean` reference](../refs/clean.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
