"""Regenerate synthetic fixtures only. No network access or real course data."""

from copy import deepcopy
from pathlib import Path

from stepik_author_tools import load_course, save_baseline
from stepik_author_tools.domain.models import Snapshot
from stepik_author_tools.serialization.jsonio import write_json


def edited_snapshot(original: Snapshot) -> Snapshot:
    """Apply the demonstration edits while retaining stable IDs and original sources."""
    remote = deepcopy(original)
    steps = {step["id"]: step for step in remote["steps"]}
    single = steps["single"]["block"]
    single["text"] = single["text"].replace("an integer?", "a string?")
    source = single.get("source")
    assert source is not None
    options = source["options"]
    options[0]["is_correct"], options[1]["is_correct"] = False, True
    code = steps["code"]["block"]
    code["text"] = code["text"].replace("print(twice(3))", "print(twice(4))")
    steps["code"]["position"], steps["practice"]["position"] = 6, 5
    # Harmless editor wrappers must not appear as a semantic difference.
    welcome = steps["welcome"]["block"]
    welcome["text"] = '<div class="editor">' + welcome["text"] + "</div>"
    return remote


def main() -> None:
    """Write reproducible fixtures for the repository's original demo course."""
    root = Path(__file__).resolve().parents[1] / "examples" / "demo"
    course = load_course(root)
    original: Snapshot = {"version": 1, "steps": course.compile()}
    write_json(root / "remote-base.json", original)
    save_baseline(course, original, root / "baseline.json")
    write_json(root / "remote-edited.json", edited_snapshot(original))


if __name__ == "__main__":
    main()
