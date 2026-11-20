"""Write SHA256SUMS for the wheel and source distributions in a release directory."""

import argparse
import hashlib
from pathlib import Path


def write_checksums(directory: Path) -> Path:
    """Hash only distributions so reruns never hash a previous checksum file or logs."""
    packages = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and (path.name.endswith(".whl") or path.name.endswith(".tar.gz"))
    )
    if not packages:
        raise ValueError(f"No wheel or source distributions found in {directory}")
    lines = []
    for package in packages:
        with package.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        lines.append(f"{digest}  {package.name}\n")
    output = directory / "SHA256SUMS"
    output.write_text("".join(lines), encoding="utf-8", newline="\n")
    return output


def main() -> int:
    """Generate the checksum manifest without requiring GitHub Actions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args()
    try:
        output = write_checksums(args.directory)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
