"""Verify that tests will import the installed package rather than the working tree."""

import sys
from importlib.util import find_spec
from pathlib import Path


def main() -> int:
    """Require the package to resolve inside the active Python environment."""
    spec = find_spec("stepik_author_tools")
    if spec is None or spec.origin is None:
        print("Error: stepik_author_tools is not installed.", file=sys.stderr)
        return 1
    origin = Path(spec.origin).resolve()
    if not origin.is_relative_to(Path(sys.prefix).resolve()):
        print(f"Error: package resolves outside the Python environment: {origin}", file=sys.stderr)
        return 1
    print(f"Installed package: {origin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
