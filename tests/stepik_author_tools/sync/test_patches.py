"""Git's default path stripping with nested Unicode paths and missing final newlines."""

import subprocess
from pathlib import Path

import pytest

from stepik_author_tools.sync.patches import render_patch


def test_git_applies_course_relative_paths_without_prefix_flags(tmp_path: Path) -> None:
    root = tmp_path / "course"
    lesson = root / "Модуль 1" / "Урок 2.md"
    lesson.parent.mkdir(parents=True)
    lesson.write_bytes(b"old")
    patch, paths = render_patch(root, {lesson: "new"})
    assert paths == ["Модуль 1/Урок 2.md"]
    assert patch.startswith('--- "a/Модуль 1/Урок 2.md"\n+++ "b/Модуль 1/Урок 2.md"\n')
    encoded = patch.encode("utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "apply", "--check", "-"], cwd=root, input=encoded, check=True)
    subprocess.run(["git", "apply", "-"], cwd=root, input=encoded, check=True)
    assert lesson.read_bytes() == b"new"


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_patch_preserves_source_encoding_and_line_endings(
    tmp_path: Path,
    bom: bytes,
    newline: str,
) -> None:
    lesson = tmp_path / "lesson.md"
    lesson.write_bytes(bom + newline.join(["old", "author note", ""]).encode())
    patch, _ = render_patch(tmp_path, {lesson: "new\nauthor note\n"})
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "apply", "--check", "-"],
        cwd=tmp_path,
        input=patch.encode(),
        check=True,
    )
    subprocess.run(["git", "apply", "-"], cwd=tmp_path, input=patch.encode(), check=True)
    assert lesson.read_bytes() == bom + newline.join(["new", "author note", ""]).encode()


def test_patch_preserves_unchanged_mixed_endings_and_unicode_separator(tmp_path: Path) -> None:
    lesson = tmp_path / "lesson.md"
    lesson.write_bytes("old\r\nauthor\u2028note\nlast\r\n".encode())
    patch, _ = render_patch(tmp_path, {lesson: "new\nauthor\u2028note\nlast\n"})
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=tmp_path, check=True)
    subprocess.run(["git", "apply", "-"], cwd=tmp_path, input=patch.encode(), check=True)
    assert lesson.read_bytes() == "new\r\nauthor\u2028note\nlast\r\n".encode()
