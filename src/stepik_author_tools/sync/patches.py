"""Render reviewable Git patches, with source paths relative to the course root."""

import json
from collections.abc import Mapping
from difflib import unified_diff
from pathlib import Path

from ..serialization.jsonio import read


def render_patch(root: Path, proposed: Mapping[Path, str]) -> tuple[str, list[str]]:
    """Describe proposed file contents without applying any of them."""
    patches: list[str] = []
    names: list[str] = []
    for path, after in proposed.items():
        before = read(path)
        if before == after:
            continue
        name = path.relative_to(root).as_posix()
        # Quoted filenames make spaces, Unicode and tabs unambiguous to git apply.
        old_name = json.dumps("a/" + name, ensure_ascii=False)
        new_name = json.dumps("b/" + name, ensure_ascii=False)
        diff = unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=old_name,
            tofile=new_name,
        )
        patches.extend(
            line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            for line in diff
        )
        names.append(name)
    return "".join(patches), names
