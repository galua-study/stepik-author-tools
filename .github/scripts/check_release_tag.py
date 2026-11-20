"""Check a release tag against the static version declared in pyproject.toml."""

import argparse
import os
import tomllib
from pathlib import Path


def check_tag(tag: str, project: Path) -> None:
    """Reject a mismatched tag, including when Python runs with optimization enabled."""
    with project.open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    expected = f"v{version}"
    if tag != expected:
        raise ValueError(f"Release tag {tag!r} must match package version: {expected}")


def main() -> int:
    """Accept an explicit tag locally or RELEASE_TAG from the release workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", nargs="?", default=os.environ.get("RELEASE_TAG"))
    parser.add_argument("--project", type=Path, default=Path("pyproject.toml"))
    args = parser.parse_args()
    if not args.tag:
        parser.error("pass a tag or set RELEASE_TAG")
    try:
        check_tag(args.tag, args.project)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Release tag {args.tag} matches the package version.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
