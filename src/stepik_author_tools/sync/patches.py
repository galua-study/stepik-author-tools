"""Render reviewable Git patches, with source paths relative to the course root."""

from collections.abc import Mapping
from difflib import SequenceMatcher, unified_diff
from io import StringIO
from pathlib import Path

# git apply strips one path component by default (-p1). These identify the two
# versions of the same course-relative file in a traditional unified diff.
GIT_SOURCE_PREFIX = "a/"
GIT_DESTINATION_PREFIX = "b/"
_UTF8_BOM = chr(0xFEFF)
_GIT_ESCAPES = {code: f"\\{code:03o}" for code in (*range(32), 127)}
_GIT_ESCAPES.update({ord('"'): '\\"', ord("\\"): "\\\\"})


def _source_format(before: str, after: str) -> str:
    # Compilation accepts UTF-8 BOM and universal newlines, but Git matches bytes.
    # Restore the source convention before generating hunk context and replacements.
    bom = _UTF8_BOM if before.startswith(_UTF8_BOM) else ""
    original = list(StringIO(before.removeprefix(bom), newline=""))
    normalized = [line.replace("\r\n", "\n").replace("\r", "\n") for line in original]
    revised = list(StringIO(after.replace("\r\n", "\n").replace("\r", "\n"), newline="\n"))
    newline = "\r\n" if "\r\n" in before else "\r" if "\r" in before else "\n"
    result = []
    for operation, start, end, new_start, new_end in SequenceMatcher(
        None, normalized, revised, autojunk=False
    ).get_opcodes():
        if operation == "equal":
            result.extend(original[start:end])
        else:
            result.extend(line.replace("\n", newline) for line in revised[new_start:new_end])
    return bom + "".join(result)


def render_patch(root: Path, proposed: Mapping[Path, str]) -> tuple[str, list[str]]:
    """Describe proposed file contents without applying any of them."""
    patches: list[str] = []
    names: list[str] = []
    for path, after in proposed.items():
        before = path.read_bytes().decode("utf-8")
        after = _source_format(before, after)
        if before == after:
            continue
        name = path.relative_to(root).as_posix()
        # Git uses C quoting for file paths, including octal escapes for control characters.
        escaped = name.translate(_GIT_ESCAPES)
        diff = unified_diff(
            list(StringIO(before, newline="\n")),
            list(StringIO(after, newline="\n")),
            fromfile=f'"{GIT_SOURCE_PREFIX}{escaped}"',
            tofile=f'"{GIT_DESTINATION_PREFIX}{escaped}"',
        )
        patches.extend(
            line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            for line in diff
        )
        names.append(name)
    return "".join(patches), names
