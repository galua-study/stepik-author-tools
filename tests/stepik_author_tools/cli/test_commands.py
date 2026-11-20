"""Behavioral regression tests for cli.commands."""

import json
from pathlib import Path

import pytest

from stepik_author_tools import (
    build,
    compare,
    read_snapshot,
)
from stepik_author_tools.cli import main
from stepik_author_tools.course.project import Course
from stepik_author_tools.serialization.jsonio import array_value, object_value
from tests.helpers import DEMO


def test_scope_and_cli_exit_codes(project: Course, tmp_path: Path) -> None:
    assert len(build(project, tmp_path / "out", "recap").steps) == 1
    assert not compare(project, read_snapshot(DEMO / "remote-edited.json"), "recap")
    assert main(["diff", str(project.root), "--remote", str(DEMO / "remote-edited.json")]) == 1
    assert main(["diff", str(project.root), "--remote", str(DEMO / "remote-base.json")]) == 0
    assert (
        main(["build", str(project.root), "--scope", "missing", "--out", str(tmp_path / "none")])
        == 2
    )


def test_json_cli_retains_difference_contract(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["diff", str(DEMO), "--remote", str(DEMO / "remote-edited.json"), "--json"])
    records = array_value(json.loads(capsys.readouterr().out), "differences")
    changes = [object_value(record) for record in records]
    assert exit_code == 1 and len(changes) == 5
    assert changes[1]["step_id"] == "single"
    assert changes[1]["field"] == "answers"
    assert changes[1]["before"] == [1] and changes[1]["after"] == [2]
