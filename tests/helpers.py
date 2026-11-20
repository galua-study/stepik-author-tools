"""Synthetic course snapshots and real Git patch application for integration tests."""

import subprocess
from pathlib import Path

from stepik_author_tools.course.project import Course
from stepik_author_tools.domain.models import Block, PullResult, Snapshot, StepSource

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo"


def snapshot(course: Course) -> Snapshot:
    return Snapshot(version=1, steps=course.compile())


def baseline(course: Course) -> Snapshot:
    return Snapshot(version=1, steps=course.compile(), kind="verified-baseline")


def apply(course: Course, result: PullResult) -> None:
    patch = course.root / "proposal.patch"
    patch.write_text(result.patch, encoding="utf-8", newline="\n")
    subprocess.run(["git", "init", "-q", str(course.root)], check=True)
    subprocess.run(["git", "apply", "--check", str(patch)], cwd=course.root, check=True)
    subprocess.run(["git", "apply", str(patch)], cwd=course.root, check=True)


def source_of(block: Block) -> StepSource:
    source = block.source
    assert source is not None
    return source
