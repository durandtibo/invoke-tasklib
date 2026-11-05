from __future__ import annotations

from invoke_tasklib.config import SCHEMA
from invoke_tasklib.config._constants import (
    CHECK_STEPS,
    DEFAULT_CHECK_STEPS,
    DEFAULT_FIX_STEPS,
    FIX_STEPS,
)

####################################
#     Tests for the step lists     #
####################################


def test_default_check_steps() -> None:
    assert DEFAULT_CHECK_STEPS == (
        "format-python",
        "format-docstrings",
        "lint",
        "types",
        "imports",
        "unit",
    )


def test_default_fix_steps() -> None:
    assert DEFAULT_FIX_STEPS == ("lint", "format-python", "format-docstrings")


def test_default_check_steps_are_the_first_check_steps() -> None:
    assert CHECK_STEPS[: len(DEFAULT_CHECK_STEPS)] == DEFAULT_CHECK_STEPS


def test_default_fix_steps_are_the_first_fix_steps() -> None:
    assert FIX_STEPS[: len(DEFAULT_FIX_STEPS)] == DEFAULT_FIX_STEPS


def test_default_check_tasks_are_derived_from_the_default_steps() -> None:
    assert SCHEMA["check"]["tasks"].default == DEFAULT_CHECK_STEPS


def test_default_fix_tasks_are_derived_from_the_default_steps() -> None:
    assert SCHEMA["fix"]["tasks"].default == DEFAULT_FIX_STEPS
