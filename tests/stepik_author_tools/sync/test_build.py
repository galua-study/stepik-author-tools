"""Behavioral regression tests for sync.build."""

from pathlib import Path

import pytest

from stepik_author_tools import (
    build,
    load_course,
    prepare_pull,
    read_snapshot,
    save_baseline,
)
from stepik_author_tools.course.project import Course
from stepik_author_tools.serialization.jsonio import load_json
from tests.helpers import DEMO, snapshot, source_of


def test_build_keys_order_code_and_privacy(project: Course, tmp_path: Path) -> None:
    built = build(project, tmp_path / "out")
    assert len(list((tmp_path / "out").glob("*.step"))) == 7
    blocks = [s.block for s in built.steps]
    assert [b.name for b in blocks] == [
        "text",
        "choice",
        "choice",
        "matching",
        "text",
        "text",
        "text",
    ]
    assert [o.is_correct for o in source_of(blocks[2]).options] == [True, False, True, False]
    assert source_of(blocks[1]).preserve_order is True
    assert "language-python" in blocks[4].text
    assert "return value * 2" in blocks[4].text
    assert "assert increment(-1)" in blocks[5].text
    assert all(
        "LOCAL AUTHOR NOTE" not in b.text and "PRIVATE DEMO KEY" not in b.text for b in blocks
    )
    assert "return value + 1" not in blocks[5].text
    assert all(b.feedback_correct == b.feedback_wrong == "" for b in blocks)


def test_baseline_refuses_edited_remote(project: Course, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="differ"):
        save_baseline(project, read_snapshot(DEMO / "remote-edited.json"), tmp_path / "base.json")
    assert not (tmp_path / "base.json").exists()
    assert (
        save_baseline(project, snapshot(project), tmp_path / "base.json").kind
        == "verified-baseline"
    )
    with pytest.raises(ValueError, match="baseline"):
        prepare_pull(project, snapshot(project), snapshot(project))


def test_stale_build_fails_without_leaving_mixed_scope(project: Course, tmp_path: Path) -> None:
    build(project, tmp_path / "out")
    with pytest.raises(ValueError, match="stale"):
        build(project, tmp_path / "out", "recap")


def test_build_retains_original_snapshot_contract(tmp_path: Path) -> None:
    assert build(load_course(DEMO), tmp_path) == read_snapshot(DEMO / "remote-base.json")
    assert load_json(tmp_path / "local-snapshot.json") == load_json(DEMO / "remote-base.json")
