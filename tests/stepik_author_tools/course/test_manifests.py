"""Manifest discovery among baselines, snapshots and multiple courses."""

from pathlib import Path

import pytest

from stepik_author_tools import load_course, load_settings
from stepik_author_tools.course.project import Course


def test_renamed_manifest_is_discovered_next_to_snapshots(project: Course) -> None:
    assert project.manifest_path
    renamed = project.manifest_path.rename(project.root / "Основы Python.JSON")
    assert load_course(project.root).manifest_path == renamed
    assert load_course(renamed).compile() == project.compile()


def test_ambiguous_directory_accepts_explicit_path_or_preferred_name(project: Course) -> None:
    assert project.manifest_path
    first = project.manifest_path.rename(project.root / "first.json")
    second = project.root / "second.json"
    second.write_bytes(first.read_bytes())
    with pytest.raises(ValueError, match=r"first\.json.*second\.json"):
        load_course(project.root)
    assert load_course(second).manifest_path == second
    config = project.root / "author.toml"
    config.write_text('[project]\nmanifest_name = "second.json"', encoding="utf-8")
    assert load_course(project.root, settings=load_settings(config)).manifest_path == second


def test_preferred_but_broken_manifest_is_reported(tmp_path: Path) -> None:
    (tmp_path / "course.json").write_text("{}", encoding="utf-8")
    (tmp_path / "other.json").write_text('{"version":1,"topics":[]}', encoding="utf-8")
    with pytest.raises(ValueError, match="topics"):
        load_course(tmp_path)
