"""Install exactly one built distribution, with test dependencies, on Windows or Linux."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def select_distribution(directory: Path, pattern: str) -> Path:
    """Fail before pip runs if the requested artifact is missing or ambiguous."""
    packages = sorted(path for path in directory.glob(pattern) if path.is_file())
    if len(packages) != 1:
        raise ValueError(
            f"Expected exactly one distribution matching {pattern!r} in {directory}; "
            f"found {len(packages)}"
        )
    return packages[0].resolve()


def main() -> int:
    """Use an explicit glob locally or DISTRIBUTION from the CI matrix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pattern", nargs="?", default=os.environ.get("DISTRIBUTION"))
    parser.add_argument("--directory", type=Path, default=Path("dist"))
    args = parser.parse_args()
    if not args.pattern:
        parser.error("pass a distribution glob or set DISTRIBUTION")
    try:
        package = select_distribution(args.directory, args.pattern)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", f"{package}[test]"], check=False
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
