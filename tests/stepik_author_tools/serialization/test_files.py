"""Round trips for snapshots and author exports read from disk."""

import json
from pathlib import Path

import pytest

from stepik_author_tools import read_snapshot
from stepik_author_tools.domain.models import JsonObject


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
def test_invalid_snapshots_fail_at_the_boundary(value: object, tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError):
        read_snapshot(path)


def test_round_trip_preserves_extension_settings_and_omitted_fields(tmp_path: Path) -> None:
    raw: JsonObject = {
        "version": 1,
        "steps": [
            {
                "stepik_id": 2,
                "lesson": 1,
                "position": 1,
                "block": {
                    "name": "choice",
                    "text": "Pick",
                    "source": {
                        "options": [{"text": "A", "is_correct": True}],
                        "future_setting": {"enabled": True},
                    },
                },
            }
        ],
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(raw), encoding="utf-8-sig")
    snapshot = read_snapshot(path)
    assert snapshot.to_dict(exclude_unset=True) == raw
    path.write_text(snapshot.model_dump_json(exclude_unset=True), encoding="utf-8")
    assert read_snapshot(path) == snapshot


def test_author_export_translates_identity_without_inventing_local_paths(tmp_path: Path) -> None:
    path = tmp_path / "export.json"
    path.write_text(
        json.dumps(
            {
                "step-sources": [
                    {
                        "id": 2,
                        "lesson": 1,
                        "position": 3,
                        "block": {"name": "text", "text": "<p>Demo</p>"},
                        "unrelated_api_metadata": "ignored",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    snapshot = read_snapshot(path)
    step = snapshot.steps[0]
    assert (step.stepik_id, step.lesson, step.position) == (2, 1, 3)
    assert step.id == "" and step.paths == []


def test_partial_paginated_author_export_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "page.json"
    path.write_text('{"step-sources": [], "meta": {"has_next": true}}', encoding="utf-8")
    with pytest.raises(ValueError, match="complete"):
        read_snapshot(path)
