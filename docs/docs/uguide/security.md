# Security

:book: This page describes the `invoke_tasklib.security` module.

## Overview

| Task             | Behavior                                                            |
| ---------------- | ------------------------------------------------------------------- |
| `security.audit` | Audits installed dependencies for known vulnerabilities (read-only) |

## Usage

```shell
invoke security.audit
```

This runs `uv run pip-audit`, which checks the currently installed dependencies against known
vulnerability databases (via [PyPI's Advisory Database](https://github.com/pypa/advisory-database))
and exits non-zero if any known vulnerability is found.

Since it audits _installed_ packages, run [`env.install`](env.md) first if dependencies haven't
been installed yet.

## See Also

- [Env](env.md): `env.install` to install the dependencies this task audits.
- [`invoke_tasklib.security` reference](../refs/security.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
