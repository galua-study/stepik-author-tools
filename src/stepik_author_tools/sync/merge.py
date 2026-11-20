"""Pure three-way merge rules: atomic grading fields and independent HTML blocks."""

from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TypeVar

from ..domain.models import Conflict, SemanticStep
from ..markdown.markup import blocks
from ..serialization.jsonio import json_value

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


def make_conflict(
    step_id: str, field: str, base: object = None, local: object = None, remote: object = None
) -> Conflict:
    """Create a serializable conflict record without losing three-way evidence."""
    return Conflict(
        step_id=step_id,
        field=field,
        base=json_value(base),
        local=json_value(local),
        remote=json_value(remote),
    )


def _merge_field(
    step_id: str,
    field: str,
    base: T,
    local: T,
    remote: T,
    conflicts: list[Conflict],
    *,
    editable: bool = True,
    merge: Callable[[T, T, T], tuple[T, bool]] = merge_value,
) -> T:
    value, clash = merge(base, local, remote)
    if clash:
        conflicts.append(make_conflict(step_id, field, base, local, remote))
    elif not editable and value != local:
        message = field + " has no editable Markdown representation"
        conflicts.append(make_conflict(step_id, message, base, local, remote))
    return value


def merge_semantics(
    step_id: str, base: SemanticStep, local: SemanticStep, remote: SemanticStep
) -> tuple[SemanticStep, list[Conflict]]:
    """Merge typed fields; callers discard the entire step if any field conflicts."""
    conflicts: list[Conflict] = []
    if base.kind != local.kind or local.kind != remote.kind:
        return local, [
            make_conflict(step_id, "step type change", base.kind, local.kind, remote.kind)
        ]
    merged = SemanticStep(
        kind=local.kind,
        body=_merge_field(
            step_id, "body", base.body, local.body, remote.body, conflicts, merge=merge_body
        ),
        options=_merge_field(
            step_id, "options", base.options, local.options, remote.options, conflicts
        ),
        answers=_merge_field(
            step_id, "answers", base.answers, local.answers, remote.answers, conflicts
        ),
        pairs=_merge_field(step_id, "pairs", base.pairs, local.pairs, remote.pairs, conflicts),
        settings=_merge_field(
            step_id,
            "settings",
            base.settings,
            local.settings,
            remote.settings,
            conflicts,
            editable=False,
        ),
        feedback=_merge_field(
            step_id,
            "feedback",
            base.feedback,
            local.feedback,
            remote.feedback,
            conflicts,
            editable=False,
        ),
    )
    return merged, conflicts
