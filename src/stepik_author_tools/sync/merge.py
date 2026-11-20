"""Pure three-way merge rules: atomic grading fields and independent HTML blocks."""

from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TypeVar

from ..domain.enums import SemanticField
from ..domain.models import Conflict, SemanticStep
from ..markdown.markup import blocks

T = TypeVar("T")


def merge_value(base: T, local: T, remote: T) -> tuple[T, bool]:
    """Select a non-conflicting three-way value, preserving local on conflict."""
    if local == remote or remote == base:
        return local, False
    if local == base:
        return remote, False
    return local, True


@dataclass(frozen=True)
class BlockEdit:
    """Replace a half-open interval in the common ancestor's HTML block sequence."""

    start: int
    end: int
    replacement: tuple[str, ...]

    def overlaps(self, other: "BlockEdit") -> bool:
        """Treat insertions on an edited boundary as conservative conflicts."""
        intervals_overlap = max(self.start, other.start) < min(self.end, other.end)
        inserted_here = self.start == self.end and other.start <= self.start <= other.end
        inserted_there = other.start == other.end and self.start <= other.start <= self.end
        return intervals_overlap or inserted_here or inserted_there


def _edits(base: list[str], changed: list[str]) -> list[BlockEdit]:
    matcher = SequenceMatcher(None, base, changed, autojunk=False)
    return [
        BlockEdit(start, end, tuple(changed[new_start:new_end]))
        for operation, start, end, new_start, new_end in matcher.get_opcodes()
        if operation != "equal"
    ]


def merge_body(base: str, local: str, remote: str) -> tuple[str, bool]:
    """Merge independent paragraphs, treating an entire code block as one unit."""
    value, conflict = merge_value(base, local, remote)
    if not conflict:
        return value, False
    original = blocks(base)
    combined = _edits(original, blocks(local))
    for edit in _edits(original, blocks(remote)):
        if edit in combined:
            continue
        if any(edit.overlaps(existing) for existing in combined):
            return local, True
        combined.append(edit)
    for edit in sorted(combined, key=lambda item: (item.start, item.end), reverse=True):
        original[edit.start : edit.end] = edit.replacement
    return "".join(original), False


def _merge_field(
    field: SemanticField,
    base: T,
    local: T,
    remote: T,
    conflicts: dict[SemanticField, str],
    *,
    editable: bool = True,
    merge: Callable[[T, T, T], tuple[T, bool]] = merge_value,
) -> T:
    value, clash = merge(base, local, remote)
    if clash:
        conflicts[field] = "Changed locally and on Stepik"
    elif not editable and value != local:
        conflicts[field] = "No editable Markdown representation"
    return value


def merge_semantics(
    step_id: str, base: SemanticStep, local: SemanticStep, remote: SemanticStep
) -> tuple[SemanticStep, list[Conflict]]:
    """Merge typed fields; callers discard the entire step if any field conflicts."""
    conflicts: dict[SemanticField, str] = {}
    # Keys address option positions: a key from one side cannot safely refer to
    # an independently edited option list on the other side.
    _, grading_clash = merge_value(
        (base.options, base.answers),
        (local.options, local.answers),
        (remote.options, remote.answers),
    )
    if grading_clash:
        conflicts[SemanticField.OPTIONS] = "Options and their answer key changed on both sides"
    if base.kind != local.kind or local.kind != remote.kind:
        return local, [
            Conflict(
                step_id=step_id,
                field=SemanticField.KIND,
                reason="Step type changed",
                base=base.kind,
                local=local.kind,
                remote=remote.kind,
            )
        ]
    merged = SemanticStep(
        kind=local.kind,
        body=_merge_field(
            SemanticField.BODY, base.body, local.body, remote.body, conflicts, merge=merge_body
        ),
        options=_merge_field(
            SemanticField.OPTIONS, base.options, local.options, remote.options, conflicts
        ),
        answers=_merge_field(
            SemanticField.ANSWERS, base.answers, local.answers, remote.answers, conflicts
        ),
        pairs=_merge_field(SemanticField.PAIRS, base.pairs, local.pairs, remote.pairs, conflicts),
        settings=_merge_field(
            SemanticField.SETTINGS,
            base.settings,
            local.settings,
            remote.settings,
            conflicts,
            editable=False,
        ),
        feedback=_merge_field(
            SemanticField.FEEDBACK,
            base.feedback,
            local.feedback,
            remote.feedback,
            conflicts,
            editable=False,
        ),
    )
    if not conflicts:
        return merged, []
    previous, current, online = base.to_dict(), local.to_dict(), remote.to_dict()
    return merged, [
        Conflict(
            step_id=step_id,
            field=field,
            reason=reason,
            base=previous[field],
            local=current[field],
            remote=online[field],
        )
        for field, reason in conflicts.items()
    ]
