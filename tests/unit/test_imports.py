from __future__ import annotations

from invoke.config import Config
from invoke.context import MockContext
from invoke.runners import Result

from invoke_tasklib import imports


def _context(tasklib_config: dict | None = None, run: object = True) -> MockContext:
    overrides = {"tasklib": tasklib_config} if tasklib_config is not None else {}
    return MockContext(config=Config(overrides=overrides), run=run)


def _commands(c: MockContext) -> list[str]:
    return [call.args[0] for call in c.run.call_args_list]


def test_check_cycles() -> None:
    discover_cmd = (
        "python -c 'import importlib, pkgutil, sys\n"
        "name = sys.argv[1]\n"
        "package = importlib.import_module(name)\n"
        "names = [name] + sorted(\n"
        "    n for _, n, ispkg in pkgutil.walk_packages(package.__path__, prefix=f'\"'\"'{name}.'\"'\"')\n"
        "    if ispkg\n"
        ")\n"
        "print('\"'\"'\\n'\"'\"'.join(names))\n"
        "' mypkg"
    )
    c = _context(
        tasklib_config={"package": {"name": "mypkg"}},
        run={
            discover_cmd: Result(stdout="mypkg\nmypkg.sub\n"),
            "python -c 'import mypkg'": Result(),
            "python -c 'import mypkg.sub'": Result(),
        },
    )
    imports.check_cycles(c)
    commands = _commands(c)
    assert commands[0] == discover_cmd
    assert commands[1:] == ["python -c 'import mypkg'", "python -c 'import mypkg.sub'"]
