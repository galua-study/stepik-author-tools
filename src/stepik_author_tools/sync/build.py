"""Write editor import files and establish verified synchronization baselines."""

from collections.abc import Sequence
from pathlib import Path

from ..course.project import Course
from ..domain.models import JsonValue, Snapshot
from ..serialization.files import JSON_SUFFIX, protect_inputs, write_json
from ..serialization.outputs import staged_outputs
from .comparison import compare


def build(
    course: Course,
    output: str | Path,
    scope: str | None = None,
    *,
    extra_inputs: Sequence[Path] = (),
) -> Snapshot:
    """Compile every selected source before writing deterministic .step exports."""
    steps = course.compile(scope)
    output = Path(output)
    names = [f"{index:03d}-{step.position:02d}.step" for index, step in enumerate(steps, 1)]
    protect_inputs(
        [output / name for name in [*names, "local-snapshot.json", "index.json"]],
        [*course.input_paths(), *extra_inputs],
    )
    snapshot = Snapshot(version=1, steps=steps)
    with staged_outputs(output, [*names, "local-snapshot.json", "index.json"]) as stage:
        if any(path.name not in names for path in output.glob("*.step")):
            raise ValueError("Output contains stale .step files; choose an empty output directory")
        _write_build(stage, snapshot, names)
    return snapshot


def _write_build(output: Path, snapshot: Snapshot, names: list[str]) -> None:
    exports: list[JsonValue] = []
    for name, step in zip(names, snapshot.steps, strict=True):
        # IDs are metadata, never filesystem paths derived from untrusted input
        write_json(
            output / name, {"block": step.block.to_dict(exclude_unset=True), "has_review": False}
        )
        exports.append(
            {"file": name, "id": step.id, "topic": step.topic, "position": step.position}
        )
    write_json(output / f"local-snapshot{JSON_SUFFIX}", snapshot.to_dict(exclude_unset=True))
    write_json(output / f"index{JSON_SUFFIX}", exports)


def save_baseline(
    course: Course, remote: Snapshot, path: str | Path, scope: str | None = None
) -> Snapshot:
    """Save the common ancestor only when local and remote semantics agree."""
    protect_inputs([Path(path)], course.input_paths())
    if compare(course, remote, scope):
        raise ValueError("Cannot establish baseline: local and remote differ")
    baseline = Snapshot(version=1, kind="verified-baseline", steps=course.compile(scope))
    target = Path(path)
    with staged_outputs(target.parent, [target.name]) as stage:
        write_json(stage / target.name, baseline.to_dict(exclude_unset=True))
    return baseline
