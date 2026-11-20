"""Argument definitions and typed parsing; no course operations occur here."""

import argparse
from collections.abc import Sequence
from pathlib import Path


class Arguments(argparse.Namespace):
    """Typed destination for argparse's externally supplied options."""

    command: str
    project: Path
    scope: str | None = None
    out: Path | None = None
    remote: Path | None = None
    live: bool = False
    json: bool = False
    save_baseline: Path | None = None
    base: Path | None = None


def _add_remote_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--remote", type=Path, help="offline snapshot or step-sources response")
    group.add_argument(
        "--live", action="store_true", help="read Stepik using optional STEPIK_TOKEN"
    )


def parse_arguments(argv: Sequence[str] | None = None) -> Arguments:
    """Parse the established three-command interface into typed attributes."""
    parser = argparse.ArgumentParser(
        description="Build Stepik imports, compare, and prepare safe local patches"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "diff", "pull"):
        command = subcommands.add_parser(name)
        command.add_argument(
            "project",
            type=Path,
            help="course.json, project directory, or topic/module map directory",
        )
        command.add_argument("--scope", help="exact topic or module ID")
        if name == "build":
            command.add_argument("--out", type=Path, required=True)
            continue
        _add_remote_arguments(command)
        if name == "diff":
            command.add_argument("--json", action="store_true")
            command.add_argument("--save-baseline", type=Path)
        else:
            command.add_argument("--base", type=Path, required=True)
            command.add_argument(
                "--out",
                type=Path,
                required=True,
                help="patch path; conflicts written alongside as .json",
            )
    return parser.parse_args(argv, namespace=Arguments())
