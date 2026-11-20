"""Behavioral regression tests for sync.pull."""

from stepik_author_tools import (
    compare,
    load_course,
    prepare_pull,
    read_snapshot,
)
from stepik_author_tools.course.project import Course
from stepik_author_tools.markdown.material import Material
from tests.helpers import DEMO, apply, baseline, snapshot, source_of


def test_remote_paragraph_local_explanation_and_reorder_merge(project: Course) -> None:
    base = baseline(project)
    path = project.root / "single.md"
    path.write_text(path.read_text() + "\nNew local author explanation.\n", encoding="utf-8")
    remote = read_snapshot(DEMO / "remote-edited.json")
    proposal = prepare_pull(project, remote, base)
    assert not proposal.conflicts
    assert "a string?" not in path.read_text()  # Proposal only.
    apply(project, proposal)
    assert "New local author explanation." in path.read_text()
    assert "LOCAL AUTHOR NOTE" in path.read_text()
    assert "a string?" in path.read_text()
    assert not compare(load_course(project.root), remote)


def test_same_paragraph_conflict_preserves_local_and_author_notes(project: Course) -> None:
    base = baseline(project)
    path = project.root / "single.md"
    path.write_text(
        path.read_text().replace("an integer?", "a list?") + "\nLocal note.\n", encoding="utf-8"
    )
    proposal = prepare_pull(project, read_snapshot(DEMO / "remote-edited.json"), base)
    assert any(c.step_id == "single" and c.field == "body" for c in proposal.conflicts)
    apply(project, proposal)
    assert "a list?" in path.read_text() and "Local note." in path.read_text()
    assert source_of(Material(path.read_text()).compile()).options[0].is_correct


def test_matching_options_and_settings_changes(project: Course) -> None:
    remote = snapshot(project)
    pairs = source_of(remote.steps[3].block).pairs
    pairs[0].second, pairs[1].second = pairs[1].second, pairs[0].second
    source_of(remote.steps[1].block).options[2].text = "<code>[4, 5]</code>"
    proposal = prepare_pull(project, remote, baseline(project))
    assert not proposal.conflicts
    apply(project, proposal)
    assert not compare(project, remote)
    source_of(remote.steps[1].block).preserve_order = False
    proposal = prepare_pull(project, remote, baseline(project))
    assert any("settings" in c.field for c in proposal.conflicts)


def test_deletion_and_cross_topic_moves_are_review_only(project: Course) -> None:
    remote = snapshot(project)
    remote.steps.pop(1)
    remote.steps[0].lesson = 999999
    proposal = prepare_pull(project, remote, baseline(project))
    assert len(proposal.conflicts) == 2 and not proposal.patch
