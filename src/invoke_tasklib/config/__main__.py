r"""Print the JSON schema (``python -m invoke_tasklib.config``)."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from invoke_tasklib.config._schema import json_schema

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str]) -> int:
    r"""Print the JSON schema of the ``tasklib`` config.

    It is run with ``python -m invoke_tasklib.config``.

    Args:
        argv: The command line arguments, without the program name.
            There must be none.

    Returns:
        The exit code: 0 on success, 2 if there are arguments.

    Example usage:

    ```pycon
    >>> from invoke_tasklib.config.__main__ import main
    >>> _ = main(["--bad"])
    usage: python -m invoke_tasklib.config

    ```
    """
    if argv:
        sys.stdout.write("usage: python -m invoke_tasklib.config\n")
        return 2
    sys.stdout.write(json.dumps(json_schema(), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
