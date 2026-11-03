# Security Policy

## Supported Versions

Security fixes are only released for the latest minor version on PyPI. Older versions are not
patched, so please upgrade to the latest release before reporting an issue.

## Reporting a Vulnerability

The `invoke-tasklib` team takes security bugs seriously. We appreciate your efforts to responsibly
disclose your findings.

### Where to Report

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report security vulnerabilities privately using
[GitHub Security Advisories](https://github.com/durandtibo/invoke-tasklib/security/advisories/new).

### What to Expect

- We will acknowledge receipt of your report within **5 business days**.
- We will provide an initial assessment (including whether the report is accepted, and an
  estimated timeline for a fix) within **10 business days** of acknowledgment.

### What to Include

Please include the following information in your report:

- Type of issue (e.g., command injection, arbitrary file deletion, information disclosure, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit the issue

This information will help us triage your report more quickly.

### Security Update Policy

- Security updates will be released as soon as possible
- Security updates will be clearly marked in release notes
- We will notify users through GitHub releases and other appropriate channels

## Known Security Considerations

`invoke-tasklib` provides reusable [Invoke](https://www.pyinvoke.org/) tasks that run shell
commands (`ruff`, `uv`, `pytest`, `mike`, ...) on your machine, with your permissions:

- **Tasks run shell commands by design**: tasks call `Context.run` to execute external tools, and
  some of them change or publish things (`clean` deletes files, `doc.publish-dev` and
  `doc.publish-latest` push to the repository, `release.publish` publishes a package). Read what a
  task does (see the user guide) before running it, and only run tasks from a `tasks.py` you trust.
- **Configuration values are quoted, but still come from you**: values read from the `tasklib`
  section of `invoke.yaml` (the paths, the documentation configuration file, the dependency groups)
  and from command line flags are quoted before they are inserted into a shell command line, so a
  space or a `;` in a value does not split or inject a command. They still choose which files and
  options the tools use, so **only use a configuration file that you trust**, and never build it
  from untrusted input (a pull request from a fork, a user-supplied value, a network payload).
- **Credentials for publishing**: `release.publish` and the documentation publishing tasks rely on the
  credentials available in your environment (PyPI token, Git remote access). Prefer short-lived
  credentials or [trusted publishing](https://docs.pypi.org/trusted-publishers/), and do not
  expose them to jobs that run untrusted code.
- **Dependency vulnerabilities**: `security.audit` audits the installed dependencies with
  `pip-audit`. It only reports the vulnerabilities known to the advisory database and does not
  replace keeping your dependencies up to date.
- **Sensitive data in output**: tasks stream the output of the commands they run to the terminal
  and to the logs. Avoid putting secrets in command line arguments or in configuration values,
  as they may end up in the CI logs.
