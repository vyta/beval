"""Enable ``python -m beval`` execution."""

import os
import sys

from beval.cli import main


def console_main() -> int:
    """Entry point that handles BrokenPipeError gracefully."""
    try:
        return main()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 1


if __name__ == "__main__":
    sys.exit(console_main())
