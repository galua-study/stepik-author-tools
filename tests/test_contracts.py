"""External data validation and output compatibility across the package refactor."""

import json
from pathlib import Path

import pytest

from stepik_author_tools import build, load_course, read_snapshot
from stepik_author_tools.cli import main
from stepik_author_tools.serialization.jsonio import array_value, object_value
from stepik_author_tools.serialization.schemas import (
    normalize_snapshot,
    parse_block,
    parse_manifest,
)
from stepik_author_tools.sync.semantic import semantic_block

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo"


def test_build_retains_original_snapshot_contract(tmp_path: Path) -> None:
    assert build(load_course(DEMO), tmp_path) == read_snapshot(DEMO / "remote-base.json")


def test_json_cli_retains_difference_contract(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["diff", str(DEMO), "--remote", str(DEMO / "remote-edited.json"), "--json"])
    records = array_value(json.loads(capsys.readouterr().out), "differences")
    changes = [object_value(record) for record in records]
    assert exit_code == 1 and len(changes) == 5
    assert changes[1]["step_id"] == "single"
    assert changes[1]["field"] == "answers"
    assert changes[1]["before"] == [1] and changes[1]["after"] == [2]


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"version": 1, "steps": "not an array"},
        {
            "version": 1,
            "steps": [
                {
                    "stepik_id": True,
                    "lesson": 1,
                    "position": 1,
                    "block": {"name": "text", "text": "hello"},
                }
            ],
        },
        {
            "step-sources": [
                {
                    "id": 1,
                    "lesson": 1,
                    "position": 1,
                    "block": {"name": "choice", "text": "pick", "source": {"options": 3}},
                }
            ]
        },
    ],
)
def test_invalid_snapshots_fail_at_the_boundary(value: object) -> None:
    with pytest.raises(ValueError):
        normalize_snapshot(value)


@pytest.mark.parametrize(
    "value",
    [
        {"version": 1, "topics": "bad"},
        {"version": 1, "topics": [{"id": "topic", "steps": [{"id": "step"}]}]},
        {"version": 1, "topics": [{"id": "topic", "lesson_id": True, "steps": []}]},
    ],
)
def test_invalid_manifests_fail_at_the_boundary(value: object) -> None:
    with pytest.raises(ValueError):
        parse_manifest(value)


def test_unknown_source_settings_remain_visible_to_comparison() -> None:
    block = parse_block(
        {"name": "text", "text": "hello", "source": {"future_setting": {"enabled": True}}}
    )
    assert semantic_block(block).to_dict()["settings"] == {"future_setting": {"enabled": True}}
