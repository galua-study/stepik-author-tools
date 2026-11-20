"""Coordinate identity checks, semantic merges and local patch proposals."""

from pathlib import Path

from ..course.project import Course
from ..domain.enums import StructureField
from ..domain.models import Conflict, PullResult, Snapshot, StepRecord
from ..serialization.files import read_text
from .merge import merge_semantics
from .ordering import merge_order
from .patches import render_patch
from .projection import project_material
from .semantic import align, platform_id, semantic_block


def _identity_conflict(
    local: StepRecord, base: StepRecord | None, remote: StepRecord | None
) -> Conflict | None:
    step_id = local.id
    if base is None or base.stepik_id != local.stepik_id:
        return Conflict(
            step_id=step_id,
            field=StructureField.IDENTITY,
            reason="Missing baseline or changed identity",
        )
    if remote is None:
        return Conflict(
            step_id=step_id, field=StructureField.MISSING, reason="Review remote deletion"
        )
    if remote.lesson != local.lesson:
        return Conflict(
            step_id=step_id,
            field=StructureField.LESSON,
            reason="Review cross-topic move",
            base=base.lesson,
            local=local.lesson,
            remote=remote.lesson,
        )
    return None


def _propose_step(
    course: Course, local: StepRecord, base: StepRecord, remote: StepRecord
) -> tuple[str | None, list[Conflict]]:
    before = semantic_block(base.block)
    current = semantic_block(local.block)
    online = semantic_block(remote.block)
    merged, conflicts = merge_semantics(local.id, before, current, online)
    # Never attach an undisputed new key to a disputed question. Other steps may
    # still be proposed, but a conflicting step stays entirely local.
    if conflicts or merged == current:
        return None, conflicts
    if len(local.paths) != 1:
        return None, [
            Conflict(
                step_id=local.id,
                field=StructureField.PATHS,
                reason="Combined source files require manual boundary review",
            )
        ]
    original = read_text(course.source_path(local.paths[0]))
    try:
        return project_material(original, current, merged, course.settings.markdown), []
    except ValueError as error:
        return None, [Conflict(step_id=local.id, field=StructureField.SOURCE, reason=str(error))]


def _material_proposals(
    course: Course, local: list[StepRecord], baseline: Snapshot, remote: dict[int, StepRecord]
) -> tuple[dict[Path, str], list[Conflict]]:
    base_by_id = {step.id: step for step in baseline.steps}
    conflicts: list[Conflict] = []
    proposed: dict[Path, str] = {}
    for step in local:
        before, other = base_by_id.get(step.id), remote.get(platform_id(step))
        if conflict := _identity_conflict(step, before, other):
            conflicts.append(conflict)
            continue
        # The identity check guarantees both sides exist before semantic merging.
        assert before is not None and other is not None
        content, step_conflicts = _propose_step(course, step, before, other)
        conflicts.extend(step_conflicts)
        if content is not None:
            proposed[course.source_path(step.paths[0])] = content
    return proposed, conflicts


def prepare_pull(
    course: Course, remote: Snapshot, baseline: Snapshot, scope: str | None = None
) -> PullResult:
    """Prepare a three-way patch and conflict report, leaving all sources untouched."""
    if baseline.kind != "verified-baseline":
        raise ValueError("pull requires a baseline saved by diff --save-baseline after a zero diff")
    local = course.compile(scope)
    alignment = align(local, remote)
    proposed, conflicts = _material_proposals(course, local, baseline, alignment.matched)
    conflicts.extend(
        Conflict(
            step_id=str(step.stepik_id),
            field=StructureField.ADDED,
            reason="Review unmapped remote addition",
        )
        for step in alignment.added
    )
    manifest, order_conflicts = merge_order(course, local, baseline, alignment.matched, scope)
    conflicts.extend(order_conflicts)
    if manifest is not None and course.manifest_path is not None:
        proposed[course.manifest_path] = (
            manifest.model_dump_json(exclude_unset=True, indent=2) + "\n"
        )
    patch, names = render_patch(course.root, proposed)
    return PullResult(patch=patch, conflicts=conflicts, changed_files=names)
