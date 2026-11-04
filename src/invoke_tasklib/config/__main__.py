r"""Print the JSON schema (``python -m invoke_tasklib.config``)."""

from __future__ import annotations

import sys

from invoke_tasklib.config._schema import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
