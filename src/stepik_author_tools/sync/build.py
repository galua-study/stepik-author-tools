"""Write editor import files and establish verified synchronization baselines."""

from pathlib import Path

from ..course.project import Course
from ..domain.models import Snapshot
from ..serialization.jsonio import write_json
from .comparison import compare


def build(course: Course, output: str | Path, scope: str | None = None) -> Snapshot:
    """Compile every selected source before writing deterministic .step exports."""
    steps = course.compile(scope)
    output = Path(output)
    names = [f"{index:03d}-{step['position']:02d}.step" for index, step in enumerate(steps, 1)]
    if any(path.name not in names for path in output.glob("*.step")):
        raise ValueError("Output contains stale .step files; choose an empty output directory")
    exports = []
    for name, step in zip(names, steps, strict=True):
        # IDs are metadata, never filesystem paths derived from untrusted input.
        write_json(output / name, {"block": step["block"], "has_review": False})
        exports.append(
            {"file": name, "id": step["id"], "topic": step["topic"], "position": step["position"]}
        )
    snapshot: Snapshot = {"version": 1, "steps": steps}
    write_json(output / "local-snapshot.json", snapshot)
    write_json(output / "index.json", exports)
    return snapshot


def save_baseline(
    course: Course, remote: Snapshot, path: str | Path, scope: str | None = None
) -> Snapshot:
    """Save the common ancestor only when local and remote semantics agree."""
    if compare(course, remote, scope):
        raise ValueError("Cannot establish baseline: local and remote differ")
    baseline: Snapshot = {"version": 1, "kind": "verified-baseline", "steps": course.compile(scope)}
    write_json(Path(path), baseline)
    return baseline
