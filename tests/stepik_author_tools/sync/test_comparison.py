"""Behavioral regression tests for sync.comparison."""

from stepik_author_tools import (
    compare,
    read_snapshot,
)
from stepik_author_tools.course.project import Course
from tests.helpers import DEMO, snapshot


def test_diff_names_real_changes_and_ignores_editor_noise(project: Course) -> None:
    changes = compare(project, read_snapshot(DEMO / "remote-edited.json"))
    assert {(c.step_id, c.field) for c in changes} == {
        ("single", "body"),
        ("single", "answers"),
        ("code", "body"),
        ("code", "position"),
        ("practice", "position"),
    }
    assert any("print(twice(4))" in c.detail for c in changes)


def test_identity_is_not_inferred_from_position(project: Course) -> None:
    remote = snapshot(project)
    remote.steps[0].stepik_id = 999999
    changes = compare(project, remote)
    assert {c.field for c in changes} == {"added", "missing"}
