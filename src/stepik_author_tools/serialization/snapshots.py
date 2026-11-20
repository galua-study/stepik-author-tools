"""Pydantic adapters for offline snapshots and Stepik author-source envelopes."""

from pathlib import Path

from ..domain.models import Snapshot
from ..domain.stepik import AuthorSteps
from .jsonio import load_json, object_value


def normalize_snapshot(value: object) -> Snapshot:
    """Read either the application's snapshot or a Stepik author-source envelope."""
    data = object_value(value, "snapshot")
    if "step-sources" in data:
        return AuthorSteps.model_validate(data).to_snapshot()
    return Snapshot.model_validate(data)


def read_snapshot(path: str | Path) -> Snapshot:
    """Read an offline file through the same model validation as live author data."""
    return normalize_snapshot(load_json(Path(path)))
