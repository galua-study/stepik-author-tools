"""Behavioral regression tests for sync.ordering."""

from stepik_author_tools import (
    prepare_pull,
    read_snapshot,
)
from stepik_author_tools.course.project import Course
from tests.helpers import DEMO, baseline


def test_concurrent_reorder_conflict(project: Course) -> None:
    base = baseline(project)
    steps = project.manifest.topics[0].steps
    steps[0], steps[1] = steps[1], steps[0]
    proposal = prepare_pull(project, read_snapshot(DEMO / "remote-edited.json"), base)
    assert any(c.field == "order" for c in proposal.conflicts)
