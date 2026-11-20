"""Describe semantic and structural differences independently of presentation or I/O."""

import json
from difflib import unified_diff

from ..config.settings import DiffLabels
from ..course.project import Course
from ..domain.enums import SemanticField, StructureField
from ..domain.models import Change, Snapshot, StepRecord
from ..markdown.markup import blocks, code_blocks
from .semantic import align, platform_id, semantic_block


def _text_detail(before: str, after: str, labels: DiffLabels) -> tuple[str, str]:
    old_code, new_code = code_blocks(before), code_blocks(after)
    if old_code != new_code:
        label = labels.code
        diff = unified_diff(
            "\n".join(old_code).splitlines(),
            "\n".join(new_code).splitlines(),
            "local code",
            "Stepik code",
            lineterm="",
        )
    else:
        label = labels.fields[SemanticField.BODY]
        diff = unified_diff(blocks(before), blocks(after), "local HTML", "Stepik HTML", lineterm="")
    return label, "\n".join(diff)


def _content_changes(local: StepRecord, remote: StepRecord, labels: DiffLabels) -> list[Change]:
    before, after = semantic_block(local.block), semantic_block(remote.block)
    old_fields, new_fields = before.to_dict(), after.to_dict()
    changes = []
    for field in SemanticField:
        old_value = old_fields[field]
        new_value = new_fields[field]
        if old_value == new_value:
            continue
        if field is SemanticField.BODY:
            label, detail = _text_detail(before.body, after.body, labels)
        else:
            label = labels.fields[field]
            detail = (
                f"{json.dumps(old_value, ensure_ascii=False)} -> "
                f"{json.dumps(new_value, ensure_ascii=False)}"
            )
        changes.append(
            Change(
                step_id=local.id,
                position=local.position,
                field=field,
                before=old_value,
                after=new_value,
                message=label,
                detail=detail,
            )
        )
    return changes


def _step_changes(local: StepRecord, remote: StepRecord | None, labels: DiffLabels) -> list[Change]:
    if remote is None:
        return [
            Change(
                step_id=local.id,
                position=local.position,
                field=StructureField.MISSING,
                before=local.stepik_id,
                after=None,
                message=labels.missing,
            )
        ]
    changes = []
    for field, before, after in (
        (StructureField.POSITION, local.position, remote.position),
        (StructureField.LESSON, local.lesson, remote.lesson),
    ):
        if before != after:
            changes.append(
                Change(
                    step_id=local.id,
                    position=local.position,
                    field=field,
                    before=before,
                    after=after,
                    message=f"{labels.moved}: {field} {before} -> {after}",
                )
            )
    return changes + _content_changes(local, remote, labels)


def compare(course: Course, remote: Snapshot, scope: str | None = None) -> list[Change]:
    """Compare selected local materials with a complete author snapshot."""
    local = course.compile(scope)
    alignment = align(local, remote)
    changes = [
        change
        for step in local
        for change in _step_changes(
            step, alignment.matched.get(platform_id(step)), course.settings.diff
        )
    ]
    changes.extend(
        Change(
            step_id=str(step.stepik_id),
            position=step.position,
            field=StructureField.ADDED,
            before=None,
            after=step.stepik_id,
            message=course.settings.diff.added,
        )
        for step in alignment.added
    )
    return changes
