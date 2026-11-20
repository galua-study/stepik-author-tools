"""Describe semantic and structural differences independently of presentation or I/O."""

import json
from difflib import unified_diff

from ..course.project import Course
from ..domain.models import Change, Snapshot, StepRecord
from ..markdown.markup import blocks, code_blocks
from .semantic import align, platform_id, semantic_block

_LABELS = {
    "kind": "step type changed",
    "body": "student text or markup changed",
    "options": "answer options/order changed",
    "answers": "correct answer changed",
    "pairs": "matching pairs changed",
    "settings": "exercise settings changed",
    "feedback": "feedback changed",
}


def _text_detail(before: str, after: str) -> tuple[str, str]:
    old_code, new_code = code_blocks(before), code_blocks(after)
    if old_code != new_code:
        label = "code changed (including literal whitespace)"
        diff = unified_diff(
            "\n".join(old_code).splitlines(),
            "\n".join(new_code).splitlines(),
            "local code",
            "Stepik code",
            lineterm="",
        )
    else:
        label = _LABELS["body"]
        diff = unified_diff(blocks(before), blocks(after), "local HTML", "Stepik HTML", lineterm="")
    return label, "\n".join(diff)


def _content_changes(local: StepRecord, remote: StepRecord) -> list[Change]:
    before, after = semantic_block(local.block), semantic_block(remote.block)
    old_fields, new_fields = before.to_dict(), after.to_dict()
    changes = []
    for field, old_value in old_fields.items():
        new_value = new_fields[field]
        if old_value == new_value:
            continue
        if field == "body":
            label, detail = _text_detail(before.body, after.body)
        else:
            label = _LABELS[field]
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


def _step_changes(local: StepRecord, remote: StepRecord | None) -> list[Change]:
    if remote is None:
        return [
            Change(
                step_id=local.id,
                position=local.position,
                field="missing",
                before=local.stepik_id,
                after=None,
                message="step missing remotely",
            )
        ]
    changes = []
    for field, before, after in (
        ("position", local.position, remote.position),
        ("lesson", local.lesson, remote.lesson),
    ):
        if before != after:
            changes.append(
                Change(
                    step_id=local.id,
                    position=local.position,
                    field=field,
                    before=before,
                    after=after,
                    message=f"step moved: {field} {before} -> {after}",
                )
            )
    return changes + _content_changes(local, remote)


def compare(course: Course, remote: Snapshot, scope: str | None = None) -> list[Change]:
    """Compare selected local materials with a complete author snapshot."""
    local = course.compile(scope)
    alignment = align(local, remote)
    changes = [
        change
        for step in local
        for change in _step_changes(step, alignment.matched.get(platform_id(step)))
    ]
    changes.extend(
        Change(
            step_id=str(step.stepik_id),
            position=step.position,
            field="added",
            before=None,
            after=step.stepik_id,
            message="unmapped step added remotely",
        )
        for step in alignment.added
    )
    return changes
