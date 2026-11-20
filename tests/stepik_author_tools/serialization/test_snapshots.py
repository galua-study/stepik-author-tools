"""Boundary and behavior contracts for serialization/test_snapshots.py."""

import pytest

from stepik_author_tools.domain.models import JsonObject
from stepik_author_tools.serialization.jsonio import json_value
from stepik_author_tools.serialization.snapshots import normalize_snapshot


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


def test_round_trip_preserves_extension_settings_and_omitted_fields() -> None:
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
    snapshot = normalize_snapshot(raw)
    assert json_value(snapshot) == raw
    assert normalize_snapshot(json_value(snapshot)) == snapshot


def test_author_export_translates_identity_without_inventing_local_paths() -> None:
    snapshot = normalize_snapshot(
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
    )
    step = snapshot.steps[0]
    assert (step.stepik_id, step.lesson, step.position) == (2, 1, 3)
    assert step.id == "" and step.paths == []
