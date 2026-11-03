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
  `.benchmarks`, `.mypy_cache`, `.tox`, `.nox`, `.hypothesis`, and `site` only if the project has a
  `mkdocs.yml` or `docs/mkdocs.yml` file (what produces it)
- Glob-matched directories: `*.egg-info` (at the root and in `src`) and every `__pycache__`
  directory of the project. The `.venv`, `.git`, `.pytest_cache` and `node_modules` directories are never walked
  into, so nothing inside them is removed.
- Files: `.coverage`, `.coverage.*` (parallel coverage data), `coverage.xml`

Nothing is removed if the corresponding directory or file doesn't exist, so `clean` is safe to run
repeatedly (it's idempotent) and doesn't fail on an already-clean checkout. A symbolic link to a
directory is removed as a link, and the directory it points to is left untouched.

To remove only the `__pycache__` directories:

```shell
invoke clean.pycache
```

## See Also

- [`invoke_tasklib.clean` reference](../refs/clean.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
