"""Regenerate synthetic fixtures only. No network access or real course data."""

from copy import deepcopy
from pathlib import Path

from stepik_author_tools import load_course, save_baseline
from stepik_author_tools.operations import write_json

root = Path(__file__).resolve().parents[1] / "examples" / "demo"
course = load_course(root)
original = dict(version=1, steps=course.compile())
write_json(root / "remote-base.json", original)
save_baseline(course, original, root / "baseline.json")
remote = deepcopy(original)
steps = {s["id"]: s for s in remote["steps"]}
steps["single"]["block"]["text"] = steps["single"]["block"]["text"].replace("an integer?", "a string?")
options = steps["single"]["block"]["source"]["options"]
options[0]["is_correct"], options[1]["is_correct"] = False, True
steps["code"]["block"]["text"] = steps["code"]["block"]["text"].replace("print(twice(3))", "print(twice(4))")
steps["code"]["position"], steps["practice"]["position"] = 6, 5
# Harmless editor wrappers must not appear as a change.
steps["welcome"]["block"]["text"] = '<div class="editor">' + steps["welcome"]["block"]["text"] + '</div>'
write_json(root / "remote-edited.json", remote)
