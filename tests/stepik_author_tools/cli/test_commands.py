"""Behavioral regression tests for cli.commands."""

from pathlib import Path

import pytest
from pydantic import TypeAdapter

from stepik_author_tools import (
    build,
    compare,
    read_snapshot,
)
from stepik_author_tools.cli import main
from stepik_author_tools.course.project import Course
from stepik_author_tools.domain.enums import SemanticField
from stepik_author_tools.domain.models import Change
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
    changes = TypeAdapter(list[Change]).validate_json(capsys.readouterr().out)
    assert exit_code == 1 and len(changes) == 5
    assert changes[1].step_id == "single"
    assert changes[1].field is SemanticField.ANSWERS
    assert changes[1].before == [1] and changes[1].after == [2]


@pytest.mark.parametrize("target", ["single.md", "course", "baseline.json", "remote-edited.json"])
def test_pull_refuses_to_overwrite_inputs(project: Course, target: str) -> None:
    before = {path: path.read_bytes() for path in project.root.iterdir() if path.is_file()}
    assert (
        main(
            [
                "pull",
                str(project.root),
                "--remote",
                str(project.root / "remote-edited.json"),
                "--base",
                str(project.root / "baseline.json"),
                "--out",
                str(project.root / target),
            ]
        )
        == 2
    )
    assert all(path.read_bytes() == data for path, data in before.items())


def test_baseline_refuses_to_overwrite_source(project: Course) -> None:
    path = project.root / "single.md"
    before = path.read_bytes()
    assert (
        main(
            [
                "diff",
                str(project.root),
                "--remote",
                str(DEMO / "remote-base.json"),
                "--save-baseline",
                str(path),
            ]
        )
        == 2
    )
    assert path.read_bytes() == before
