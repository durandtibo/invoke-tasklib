from __future__ import annotations

import os
import shlex
import subprocess
from typing import Any

from invoke.config import Config
from invoke.context import Context
from invoke.exceptions import UnexpectedExit
from invoke.runners import Result


class SubprocessContext(Context):
    r"""A context that really runs the commands, not Invoke's runner.

    Invoke's local runner leaves file handles open under pytest, which
    pytest reports as unraisable warnings in unrelated tests.
    """

    def run(self, command: str, **kwargs: Any) -> Result:
        env = kwargs.get("env")
        if env is not None and not kwargs.get("replace_env"):
            env = {**os.environ, **env}
        proc = subprocess.run(  # noqa: S603 (commands are built by the tasks under test)
            shlex.split(command), capture_output=True, text=True, check=False, env=env
        )
        result = Result(stdout=proc.stdout, stderr=proc.stderr, exited=proc.returncode)
        if proc.returncode and not kwargs.get("warn"):
            raise UnexpectedExit(result)
        return result


def subprocess_context(tasklib_config: dict | None = None) -> SubprocessContext:
    r"""Create a context that really runs the commands.

    It is the counterpart of ``tests.helpers.make_context`` for the
    integration tests.

    Args:
        tasklib_config: The ``tasklib`` section of the config, or
            ``None`` for an empty config.

    Returns:
        The context.
    """
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return SubprocessContext(config=Config(overrides=overrides))
