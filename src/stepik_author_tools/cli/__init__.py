"""Thin CLI entry point; public library operations never import this package."""

import sys
from collections.abc import Sequence

from .arguments import parse_arguments
from .commands import run


def main(argv: Sequence[str] | None = None) -> int:
    """Return 0 for success, 1 for differences/conflicts, or 2 for invalid input."""
    args = parse_arguments(argv)
    try:
        return run(args)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
