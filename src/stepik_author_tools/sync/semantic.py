"""Normalize Stepik content and align snapshots by stable IDs, never by position."""

from dataclasses import dataclass

from ..domain.enums import StepKind
from ..domain.models import Block, SemanticStep, Snapshot, StepRecord, StepSource
from ..markdown.markup import canonical


def semantic_block(block: Block) -> SemanticStep:
    """Extract typed semantic fields, requiring author-visible grading data."""
    try:
        kind = StepKind(block.name)
    except ValueError:
        raise ValueError(f"Unsupported Stepik block: {block.name}") from None
    source = block.source or StepSource()
    options: tuple[str, ...] = ()
    answers: tuple[int, ...] = ()
    pairs: tuple[tuple[str, str], ...] = ()
    feedback: tuple[str, ...] = (block.feedback_correct, block.feedback_wrong)
    if kind is StepKind.CHOICE:
        if not source.options:
            raise ValueError("Choice source is incomplete; author step-sources access is required")
        options = tuple(canonical(option.text) for option in source.options)
        answers = tuple(i for i, option in enumerate(source.options, 1) if option.is_correct)
        feedback += tuple(option.feedback for option in source.options)
    elif kind is StepKind.MATCHING:
        if not source.pairs:
            raise ValueError("Matching source does not expose pairs")
        pairs = tuple((canonical(pair.first), canonical(pair.second)) for pair in source.pairs)
    return SemanticStep(
        kind=kind,
        body=canonical(block.text),
        options=options,
        answers=answers,
        pairs=pairs,
        settings={
            key: value
            for key, value in source.to_dict(exclude_unset=True).items()
            if key not in {"options", "pairs"}
        },
        feedback=feedback,
    )


def platform_id(step: StepRecord) -> int:
    """Require an explicit platform identity before any synchronization operation."""
    value = step.stepik_id
    if value is None:
        raise ValueError(
            "Stable stepik_id mapping required; never infer identity from position. "
            "Record the mapping in the course manifest."
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
    lessons = {step.lesson for step in local}
    topics = {step.topic for step in local}
    matched: dict[int, StepRecord] = {}
    added: list[StepRecord] = []
    seen: set[int] = set()
    positions: set[tuple[int | None, int]] = set()
    for step in snapshot.steps:
        remote_id = platform_id(step)
        if remote_id in seen:
            raise ValueError("Remote snapshot has missing/duplicate/invalid Stepik IDs")
        seen.add(remote_id)
        relevant = step.lesson in lessons or step.topic in topics or remote_id in local_ids
        if not relevant:
            continue
        _validate_remote_position(step, positions)
        semantic_block(step.block)
        if remote_id in local_ids:
            matched[remote_id] = step
        else:
            added.append(step)
    return Alignment(matched, added)


def _validate_remote_position(step: StepRecord, seen: set[tuple[int | None, int]]) -> None:
    position = step.position
    key = (step.lesson, position)
    if key in seen:
        raise ValueError("Duplicate position in remote lesson")
    seen.add(key)
