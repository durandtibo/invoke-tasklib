from __future__ import annotations

from unittest.mock import Mock

from invoke.config import Config
from invoke.context import MockContext


def make_context(tasklib_config: dict | None = None, run: object = True) -> MockContext:
    r"""Create a ``MockContext`` that records the commands it runs.

    Args:
        tasklib_config: The ``tasklib`` section of the config, or
            ``None`` for an empty config.
        run: The ``run`` argument of ``MockContext``. ``True`` makes
            every command succeed and records the calls.

    Returns:
        The mock context.
    """
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=run)


def run_kwargs(c: MockContext) -> list[dict]:
    r"""Return the keyword arguments passed to ``c.run``, in order.

    Args:
        c: A context created by ``make_context`` with ``run=True``.

    Returns:
        One dictionary of keyword arguments per call.
    """
    run = c.run
    assert isinstance(run, Mock)
    return [call.kwargs for call in run.call_args_list]


def commands(c: MockContext) -> list[str]:
    r"""Return the commands passed to ``c.run``, in order.

    Args:
        c: A context created by ``make_context`` with ``run=True``.

    Returns:
        The command strings.
    """
    run = c.run
    assert isinstance(run, Mock)
    return [call.args[0] for call in run.call_args_list]
