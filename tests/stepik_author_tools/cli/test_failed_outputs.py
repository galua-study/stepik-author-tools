"""A failed command must preserve the previous successful output."""

import json
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from stepik_author_tools.cli import main
from stepik_author_tools.course.project import Course


@pytest.mark.parametrize("operation", ["baseline", "build", "pull"])
def test_failed_write_preserves_previous_outputs(
    project: Course, tmp_path: Path, operation: str
) -> None:
    output = tmp_path / "results"
    output.mkdir()
    if operation == "baseline":
        args = [
            "diff",
            str(project.root),
            "--remote",
            str(project.root / "remote-base.json"),
            "--save-baseline",
            str(output / "base.json"),
        ]
        failing_name = "base.json"
    elif operation == "build":
        args = ["build", str(project.root), "--out", str(output)]
        failing_name = "002-02.step"
    else:
        args = [
            "pull",
            str(project.root),
            "--base",
            str(project.root / "baseline.json"),
            "--remote",
            str(project.root / "remote-edited.json"),
            "--out",
            str(output / "review"),
        ]
        failing_name = "review.json"

    assert main(args) == 0
    previous = {p.name: p.read_bytes() for p in output.iterdir()}
    if operation == "build":
        (project.root / "welcome.md").write_text("Updated welcome.", encoding="utf-8")
    if operation == "pull":
        args[args.index("--remote") + 1] = str(project.root / "remote-base.json")
    write = Path.write_text

    def interrupted(
        path: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        if path.name == failing_name:
            write(path, data[:8], encoding, errors, newline)
            raise OSError("disk full")
        return write(path, data, encoding, errors, newline)

    with patch.object(Path, "write_text", interrupted):
        assert main(args) == 2
    assert {p.name: p.read_bytes() for p in output.iterdir()} == previous
    assert main(args) == 0


def test_interrupted_rebuild_restores_every_indexed_step(project: Course, tmp_path: Path) -> None:
    output = tmp_path / "results"
    args = ["build", str(project.root), "--out", str(output)]
    assert main(args) == 0
    originals = {p.name: p.read_bytes() for p in output.iterdir()}
    (project.root / "welcome.md").write_text("New welcome.", encoding="utf-8")
    replace = Path.replace

    def interrupt_after_backup(path: Path, target: Path) -> Path:
        moved = replace(path, target)
        if path.name == "001-01.step" and target.parent.name == "previous":
            raise KeyboardInterrupt
        return moved

    with patch.object(Path, "replace", interrupt_after_backup), pytest.raises(KeyboardInterrupt):
        main(args)
    index = (output / "index.json").read_bytes()
    assert index == originals["index.json"]
    for entry in json.loads(index):
        name = entry["file"]
        assert (output / name).read_bytes() == originals[name]
    assert (output / "local-snapshot.json").read_bytes() == originals["local-snapshot.json"]
    assert main(args) == 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows read-only file attribute")
@pytest.mark.parametrize("operation", ["baseline", "build"])
def test_read_only_output_is_retryable(project: Course, tmp_path: Path, operation: str) -> None:
    output = tmp_path / "results"
    if operation == "build":
        target = output / "001-01.step"
        args = ["build", str(project.root), "--out", str(output)]
    else:
        target = output / "base.json"
        args = [
            "diff",
            str(project.root),
            "--remote",
            str(project.root / "remote-base.json"),
            "--save-baseline",
            str(target),
        ]
    assert main(args) == 0
    original = {p.name: p.read_bytes() for p in output.iterdir()}
    if operation == "build":
        (project.root / "welcome.md").write_text("New welcome.")
    target.chmod(stat.S_IREAD)
    try:
        assert main(args) == 2
    finally:
        target.chmod(stat.S_IREAD | stat.S_IWRITE)
    assert not (output / ".stepik-author-write").exists()
    assert {p.name: p.read_bytes() for p in output.iterdir()} == original
    assert main(args) == 0
    if operation == "build":
        assert target.read_bytes() != original[target.name]


def test_build_guides_retry_after_crash(
    project: Course, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "interrupted"
    previous = output / ".stepik-author-write" / "previous"
    previous.mkdir(parents=True)
    backup = previous / "index.json"
    backup.write_text("only copy")
    assert main(["build", str(project.root), "--out", str(output)]) == 2
    message = capsys.readouterr().err
    assert str(previous) in message
    assert "fresh output directory" in message
    assert backup.read_text() == "only copy"


@pytest.mark.parametrize("name", ["001-01.step", "local-snapshot.json", "index.json"])
def test_build_refuses_to_overwrite_its_config(project: Course, tmp_path: Path, name: str) -> None:
    output = tmp_path / "results"
    output.mkdir()
    profile = output / name
    original = b'[project]\nmanifest_name = "course.json"\n'
    profile.write_bytes(original)
    assert main(["build", str(project.root), "--out", str(output), "--config", str(profile)]) == 2
    assert list(output.iterdir()) == [profile]
    assert profile.read_bytes() == original
