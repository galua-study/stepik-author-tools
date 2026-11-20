"""Normalize Stepik content and align snapshots by stable IDs, never by position."""

from dataclasses import dataclass

from ..domain.models import Block, SemanticStep, Snapshot, StepRecord
from ..markdown.markup import canonical
from ..serialization.jsonio import json_value


def semantic_block(block: Block) -> SemanticStep:
    """Extract typed semantic fields, requiring author-visible grading data."""
    kind = block["name"]
    if kind not in {"text", "choice", "matching"}:
        raise ValueError(f"Unsupported Stepik block: {kind}")
    source = block.get("source") or {}
    options = source.get("options", [])
    pairs = source.get("pairs", [])
    if kind == "choice":
        if not options:
            raise ValueError("Choice source is incomplete; author step-sources access is required")
        if any(not isinstance(option.get("is_correct"), bool) for option in options):
            raise ValueError("Choice source does not expose correct answers")
    if kind == "matching" and not pairs:
        raise ValueError("Matching source does not expose pairs")
    feedback = (block.get("feedback_correct", ""), block.get("feedback_wrong", ""))
    return SemanticStep(
        kind=kind,
        body=canonical(block["text"]),
        options=tuple(canonical(option["text"]) for option in options) if kind == "choice" else (),
        answers=tuple(i for i, option in enumerate(options, 1) if option["is_correct"])
        if kind == "choice"
        else (),
        pairs=tuple((canonical(pair["first"]), canonical(pair["second"])) for pair in pairs)
        if kind == "matching"
        else (),
        settings={
            key: json_value(value)
            for key, value in source.items()
            if key not in {"options", "pairs"}
        },
        feedback=feedback + tuple(option.get("feedback", "") for option in options)
        if kind == "choice"
        else feedback,
    )


def platform_id(step: StepRecord) -> int:
    """Require an explicit platform identity before any synchronization operation."""
    value = step["stepik_id"]
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(
            "Stable stepik_id mapping required; never infer identity from position. "
            "Use course.json."
        )
    return value


@dataclass(frozen=True)
class Alignment:
    """Remote rows matched to selected local IDs and additional selected-lesson rows."""

    matched: dict[int, StepRecord]
    added: list[StepRecord]


def align(local: list[StepRecord], snapshot: Snapshot) -> Alignment:
    """Check remote identity/position uniqueness and select all relevant lesson rows."""
    local_ids = {platform_id(step) for step in local}
    lessons = {step["lesson"] for step in local}
    topics = {step["topic"] for step in local}
    matched: dict[int, StepRecord] = {}
    added: list[StepRecord] = []
    seen: set[int] = set()
    positions: set[tuple[int | None, int]] = set()
    for step in snapshot["steps"]:
        remote_id = platform_id(step)
        if remote_id in seen:
            raise ValueError("Remote snapshot has missing/duplicate/invalid Stepik IDs")
        seen.add(remote_id)
        relevant = (
            step["lesson"] in lessons or step.get("topic") in topics or remote_id in local_ids
        )
        if not relevant:
            continue
        _validate_remote_position(step, positions)
        semantic_block(step["block"])
        if remote_id in local_ids:
            matched[remote_id] = step
        else:
            added.append(step)
    return Alignment(matched, added)


def _validate_remote_position(step: StepRecord, seen: set[tuple[int | None, int]]) -> None:
    position = step["position"]
    if not isinstance(position, int) or isinstance(position, bool) or position < 1:
        raise ValueError("Remote positions must be positive integers")
    key = (step["lesson"], position)
    if key in seen:
        raise ValueError("Duplicate position in remote lesson")
    seen.add(key)
