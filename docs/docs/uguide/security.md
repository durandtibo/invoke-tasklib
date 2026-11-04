# Security

:book: This page describes the `invoke_tasklib.security` module.

## Overview

| Task             | Behavior                                                             |
| ---------------- | -------------------------------------------------------------------- |
| `security.audit` | Audits the locked dependencies for known vulnerabilities (read-only) |

## Usage

```shell
invoke security.audit
```

This exports `uv.lock` to a temporary requirements file (`uv export --locked`, with
`--all-extras` and `--all-groups`, so the packages that only an extra or a group installs are
audited too) and audits it with
`uvx --from "pip-audit>=2.10,<3" pip-audit` against known vulnerability databases (via
[PyPI's Advisory Database](https://github.com/pypa/advisory-database)). It exits non-zero if the lock
file is out of date or if a vulnerability is found.

The task does not sync or modify the environment, and the result depends on the lock file, not on
what was installed last. `pip-audit` does not have to be a dependency of the project. The tool is
run from the version range `pip-audit>=2.10,<3` (`PIP_AUDIT_REQUIREMENT` in `invoke_tasklib.security`),
so a new major release is never run without a release of `invoke-tasklib`.

Use `--args` to pass options to `pip-audit`, for example to accept an advisory:

```shell
invoke security.audit --args "--ignore-vuln PYSEC-2024-1"
```

## See Also

- [Env](env.md): `env.update` to update the lock file this task audits.
- [`invoke_tasklib.security` reference](../refs/security.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
