"""Behavioral regression tests for course.project."""

import pytest

from stepik_author_tools import (
    load_course,
)
from stepik_author_tools.course.project import Course


def test_paths_cannot_escape_the_course_root(project: Course) -> None:
    manifest = project.manifest
    manifest.topics[0].steps[0].path = "../escape.md"
    assert project.manifest_path is not None
    project.manifest_path.write_text(manifest.model_dump_json(exclude_unset=True), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes"):
        load_course(project.root)
