# Writing a Custom Task

:book: This page shows how to write a task of your own that behaves like the tasks of
`invoke-tasklib`. The helpers below are the supported public API for that: their signatures are
documented in the reference pages ([`runner`](../refs/runner.md), [`output`](../refs/output.md) and
[`config`](../refs/config.md)).

## Overview

| Helper                                | Use it to                                                            |
| ------------------------------------- | -------------------------------------------------------------------- |
| `invoke_tasklib.config.load_config`   | Read the [resolved config](config.md); an invalid one exits cleanly  |
| `invoke_tasklib.runner.build_command` | Build a command line with quoted arguments and paths                 |
| `invoke_tasklib.runner.run`           | Run a command: echo, pty only on a terminal, program check           |
| `invoke_tasklib.runner.check_program` | Check that the programs of a command are installed                   |
| `invoke_tasklib.output.say`           | Print a progress message                                             |
| `invoke_tasklib.output.step`          | Print the start and the end of a step, and `❌ Failed: ...` on error |

## Example

```python
# tasks.py
from invoke.tasks import task

from invoke_tasklib import make_ns
from invoke_tasklib.config import load_config
from invoke_tasklib.output import step
from invoke_tasklib.runner import ARGS_HELP, PATHS_HELP, build_command, run


@task(help={"args": ARGS_HELP, "paths": PATHS_HELP})
def check_complexity(c, args=None, paths=None):
    r"""Check the complexity of the code with radon."""
    cfg = load_config(c)
    with step(c, "🔍 Checking the complexity...", "✅ Complexity check passed"):
        run(c, build_command("radon cc", args=args, paths=paths, default_paths=[cfg.paths.src]))


ns = make_ns()
ns.add_task(check_complexity)
```

- **Read the config with `load_config(c)`**, not from `c.config`: it merges the defaults, validates
  the values and exits with a one-line message on an invalid config. The `tasklib` section is
  available as `cfg.package`, `cfg.paths`, `cfg.groups`, `cfg.test` and `cfg.check`.
- **Build the command with `build_command`**: the program is used as it is, and the user's `args`
  and `paths` (and the default paths) are split like a shell does and quoted, so a space or a `;`
  never splits or injects a command.
- **Run it with `run`**: it echoes the command, uses a pty only on a terminal, and first checks that
  the program is on the `PATH` (with an installation hint if it is not). Do not call `c.run`
  directly. For `python -m <module>`, the module is checked only when the command uses the running
  interpreter (`python_executable()`, the one that runs `invoke`): for another interpreter or a
  `python` found on the `PATH`, a missing module is reported by Python itself
  (`No module named ...`), without a hint. Use `python_executable()` in your commands.
- **Report the step with `step`**: it prints the start message, then the done message, or
  `❌ Failed: <what was being done>` on the error stream (stderr, like the message of an `Exit`) if
  the block raises (the exception is raised again, so the exit code is unchanged). Use `say` for any
  other message (`say(c, msg, err=True)` writes to stderr); neither fails on a terminal that cannot
  encode an emoji: `✅`, `❌` and `⏭️` become `[ok]`, `[fail]` and `[skip]`, and the other emojis are
  removed. Set `INVOKE_TASKLIB_ASCII=1` to get this output on any terminal.

Follow the naming convention of the shared tasks: `check_<target>` never modifies a file and
`fix_<target>` does. Add the task to a `make_ns()` result, as above, so it does not leak into other
importers.

```pycon
>>> from invoke_tasklib.runner import build_command
>>> build_command("radon cc", args="-s", paths="a.py 'my dir'", default_paths=["src"])
"radon cc -s a.py 'my dir'"

```

## Adding a Shortcut for an Existing Task

`add_task` with a `name` registers a task of the library under one more name, at the top level of
the collection. The task keeps its own name in its namespace:

```pycon
>>> from invoke_tasklib import make_ns
>>> from invoke_tasklib.release import build
>>> ns = make_ns()
>>> ns.add_task(build, name="build-package")
>>> "build-package" in ns.task_names
True
>>> "release.build" in ns.task_names
True

```

The `tasks.py` of this repository does it for `release.build`: `inv build-package` is the command
that the composite action `durandtibo/build-pypi-package-action` runs, as the release workflow
shows. Such a shortcut shows up in `invoke --list` of the project, so add one only for a name that
something else (a CI action, a script) depends on.

## Testing a Custom Task

`invoke.context.MockContext` records the commands without running them:

```pycon
>>> from invoke.config import Config
>>> from invoke.context import MockContext
>>> from invoke_tasklib.runner import run
>>> c = MockContext(config=Config(), run=True)
>>> _ = run(c, "ls")
>>> c.run.call_args.args[0]
'ls'

```

## See Also

- [Config](config.md): the `tasklib` section that `load_config` resolves.
- [`invoke_tasklib.runner` reference](../refs/runner.md)
- [`invoke_tasklib.output` reference](../refs/output.md)
