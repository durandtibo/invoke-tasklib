# Contributing to `invoke-tasklib`

We want to make contributing to this project as easy and transparent as possible.

## Overview

We welcome contributions from anyone, even if you are new to open source.

- If you are planning to contribute back bug-fixes, please do so without any further discussion.
- If you plan to contribute new features, new tasks, or extensions to the core, please first
  open an issue and discuss the feature with us.

Once you implement and test your feature or bug-fix, please submit a Pull Request.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Git

### Setting Up Your Development Environment

1. **Fork and clone the repository:**

   ```shell
   git clone https://github.com/YOUR-USERNAME/invoke-tasklib.git
   cd invoke-tasklib
   ```

2. **Create the virtual environment:**

   ```shell
   uv venv --clear
   ```

3. **Activate the virtual environment:**

   ```shell
   source .venv/bin/activate
   ```

4. **Install the dependencies:**

   ```shell
   uv sync --group dev
   ```

5. **Install pre-commit hooks:**
   ```shell
   pre-commit install
   ```

See the [development guide](docs/docs/dev/development.md) for more details.

## Development Workflow

### Running Tests

Run all unit tests:

```shell
inv test.unit
```

Run tests with coverage:

```shell
inv test.unit --cov
```

Run specific tests:

```shell
pytest tests/unit/test_lint.py
```

Other kinds of tests:

```shell
inv test.doctest  # doctests of the source code and of the Markdown files
inv test.all      # all the tests
```

### Code Quality

**Format your code:**

```shell
inv format.fix-python
```

**Run linter:**

```shell
inv lint.check-python
```

**Check types:**

```shell
inv types.check
```

**Format docstrings:**

```shell
inv format.fix-docstrings
```

**Run all pre-commit checks:**

```shell
pre-commit run --all-files
```

### Building Documentation

Build documentation locally:

```shell
mkdocs serve -f docs/mkdocs.yml
```

Then visit http://127.0.0.1:8000 to view the documentation.

## Pull Requests

We actively welcome your pull requests.

### Pull Request Process

1. **Fork the repo and create your branch from an up-to-date `main`:**

   ```shell
   git checkout -b feat/my-new-feature
   ```

   Name the branch `<type>/<short-description>` in lowercase kebab-case. The type is one of
   `feat`, `bugfix`, `hotfix`, `docs`, `refactor`, `perf`, `test`, `chore` or `ci`.

2. **Make your changes:**
   - Add your code
   - Write tests for new functionality
   - Update documentation if needed

3. **Ensure tests pass:**

   ```shell
   inv test.unit --cov
   ```

4. **Run code quality checks:**

   ```shell
   pre-commit run --all-files
   ```

5. **Commit your changes:**

   ```shell
   git add .
   git commit -m "Add a cache option to the test tasks"
   ```

6. **Push to your fork:**

   ```shell
   git push origin feat/my-new-feature
   ```

7. **Submit a Pull Request** through GitHub

### Pull Request Guidelines

- **Write clear commit messages:** Use a short imperative title, for example
  `Add a cache option to the test tasks`
- **Keep changes focused:** One feature or bug fix per PR
- **Add tests:** All new code should have tests
- **Update documentation:** If you change APIs or add features
- **Follow code style:** Run pre-commit hooks before committing
- **Link related issues:** Reference any related issues in your PR description
- **Keep up to date with `main`:** If your PR conflicts with `main`, merge `origin/main` into your
  branch instead of rebasing and force-pushing

### What to Include in Your PR

- **Description:** Clear explanation of what you changed and why, what you deliberately did not
  change, and any behavior change (for example a changed output, or a breaking change of a
  signature)
- **Tests:** Unit tests that cover your changes
- **Documentation:** Updates to docs if you changed behavior

## Issues

We use GitHub issues to track public bugs or feature requests.

### Reporting Bugs

When reporting bugs, please include:

1. **Clear title:** Brief description of the issue
2. **Environment information:**
   - `invoke-tasklib` version: `pip show invoke-tasklib`
   - `invoke` version: `pip show invoke`
   - Python version: `python --version`
   - Operating system
3. **Steps to reproduce:** The `invoke` command you ran, and the relevant part of your `tasks.py`
   and `invoke.yaml`
4. **Expected behavior:** What you expected to happen
5. **Actual behavior:** What actually happened
6. **Error messages:** Full error traceback if applicable

### Requesting Features

For feature requests, please include:

1. **Clear title:** Brief description of the feature
2. **Motivation:** Why this feature would be useful
3. **Proposed solution:** How you envision it working
4. **Alternatives considered:** Other approaches you've thought about
5. **Examples:** Code examples showing how it would be used

## Coding Standards

### Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting
- Use [ty](https://github.com/astral-sh/ty) for type checking
- Maximum line length: 100 characters
- Fix the issues raised by ruff and ty instead of ignoring them (`noqa`, `type: ignore`)

### Docstring Style

- Follow [Google style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- Include type hints in function signatures
- Document all functions, and update the docstrings whenever the behavior, the signature or the
  options of the code change
- Write the examples of the docstrings as `pycon` blocks that run as doctests (`inv test.doctest`),
  ending with an empty line before the closing fence

**Example:**

````python
def my_function(param1: int, param2: str) -> bool:
    """Brief description of the function.

    Longer description if needed. Explain what the function does,
    any important notes, etc.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param1 is negative.

    Example:
        ```pycon
        >>> from my_package import my_function  # doctest: +SKIP
        >>> my_function(42, "hello")  # doctest: +SKIP
        True

        ```
    """
    if param1 < 0:
        raise ValueError("param1 must be non-negative")
    return param2.startswith("h")
````

### Testing Standards

- Write unit tests for all new code, including private functions
- Unit tests mirror the source tree: the tests of `src/invoke_tasklib/<module>.py` are in
  `tests/unit/test_<module>.py`
- Cover 100% of the code you add or change, and add a regression test for every bug fixed
- Test one behavior per test, and use descriptive test names
- Use `pytest.mark.parametrize` to check the same behavior on several values
- Test edge cases and error conditions, and give `pytest.raises` a `match` for the message
- Keep unit tests fast: no sleeps, no real network or heavy I/O

**Example test:**

```python
import pytest


def test_my_function_with_negative_value_raises_value_error():
    """Test that my_function raises a ValueError for a negative value."""
    with pytest.raises(ValueError, match="param1 must be non-negative"):
        my_function(-1, "hello")
```

## Documentation

### Documentation Standards

- Update documentation for all user-facing changes
- Include code examples in documentation
- Keep documentation up-to-date with code changes
- Use clear, concise language

### Documentation Types

1. **API documentation:** Auto-generated from docstrings
2. **User guides:** One page per task module in `docs/docs/uguide/`
3. **Development guides:** Architecture and development workflow in `docs/docs/dev/`

## Commit Message Guidelines

Write a short title in the imperative mood that says what the commit does, and start it with a
verb such as `Add`, `Fix`, `Update`, `Remove`, `Improve` or `Refactor`.

**Examples:**

- `Add CLAUDE.md`
- `Fix the handling of an empty package name`
- `Update dependencies`

## Community

### Code of Conduct

Please note that this project is released with a [Code of Conduct](CODE_OF_CONDUCT.md).
By participating in this project you agree to abide by its terms.

### Getting Help

- **Documentation:** https://durandtibo.github.io/invoke-tasklib/
- **Issues:** https://github.com/durandtibo/invoke-tasklib/issues
- **Discussions:** Open an issue for questions

## License

By contributing to `invoke-tasklib`, you agree that your contributions will be licensed under the
BSD 3-Clause License as specified in the [LICENSE](LICENSE) file in the root directory
of this source tree.

## Questions?

If you have questions about contributing, feel free to:

- Open an issue with the "question" label
- Check the [documentation](https://durandtibo.github.io/invoke-tasklib/)
- Review existing issues and pull requests

Thank you for contributing to `invoke-tasklib`! 🎉
