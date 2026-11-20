"""Merge within-topic order using stable identities rather than old positions."""

from copy import deepcopy

from ..course.project import Course
from ..domain.models import Conflict, Manifest, Snapshot, StepRecord, TopicSpec
from .merge import make_conflict, merge_value
from .semantic import platform_id


def _merged_topic_order(
    topic: TopicSpec, local: list[StepRecord], baseline: Snapshot, remote: dict[int, StepRecord]
) -> tuple[list[int] | None, list[Conflict]]:
    current = [step for step in local if step.topic == topic.id]
    previous = sorted(
        [step for step in baseline.steps if step.topic == topic.id],
        key=lambda step: step.position,
    )
    online = sorted(
        [remote[platform_id(step)] for step in current if platform_id(step) in remote],
        key=lambda step: step.position,
    )
    base_ids = [platform_id(step) for step in previous]
    local_ids = [platform_id(step) for step in current]
    remote_ids = [platform_id(step) for step in online]
    same_members = set(base_ids) == set(local_ids) == set(remote_ids)
    same_lesson = all(step.lesson == topic.lesson_id for step in online)
    if not same_members or not same_lesson:
        return None, []  # Additions/deletions/cross-topic moves are reviewed by pull.
    order, clash = merge_value(base_ids, local_ids, remote_ids)
    if clash:
        return None, [make_conflict(topic.id, "order", base_ids, local_ids, remote_ids)]
    return (order if order != local_ids else None), []


def merge_order(
    course: Course,
    local: list[StepRecord],
    baseline: Snapshot,
    remote: dict[int, StepRecord],
    scope: str | None,
) -> tuple[Manifest | None, list[Conflict]]:
    """Return an updated manifest, leaving all ambiguous structural edits for review."""
    manifest = deepcopy(course.manifest)
    conflicts: list[Conflict] = []
    changed = False
    for topic in course.topics(scope):
        order, topic_conflicts = _merged_topic_order(topic, local, baseline, remote)
        conflicts.extend(topic_conflicts)
        if order is None:
            continue
        if course.manifest_path is None:
            conflicts.append(make_conflict(topic.id, "order requires an explicit course.json"))
            continue
        target = next(item for item in manifest.topics if item.id == topic.id)
        by_id = {step.stepik_id: step for step in target.steps}
        target.steps = [by_id[step_id] for step_id in order]
        changed = True
    return (manifest if changed else None), conflicts
