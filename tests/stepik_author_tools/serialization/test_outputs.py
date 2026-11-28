"""Failed publication and overlapping writers preserve the last complete set."""

from pathlib import Path
from unittest.mock import patch

import pytest

from stepik_author_tools.serialization.outputs import staged_outputs


@pytest.mark.parametrize("previous", [True, False])
def test_report_replacement_failure_rolls_back_pair(tmp_path: Path, previous: bool) -> None:
    names = ["review.patch", "review.patch.json"]
    if previous:
        for name in names:
            (tmp_path / name).write_bytes(b"previous")
    replace = Path.replace

    def fail_report(path: Path, target: Path) -> Path:
        if path.parent.name == "new" and target.name == names[-1]:
            assert (tmp_path / names[0]).read_bytes() == b"updated"
            assert not target.exists()
            raise PermissionError("cannot publish report")
        return replace(path, target)

    with (
        patch.object(Path, "replace", fail_report),
        pytest.raises(PermissionError),
        staged_outputs(tmp_path, names) as stage,
    ):
        for name in names:
            (stage / name).write_bytes(b"updated")
    expected = dict.fromkeys(names, b"previous") if previous else {}
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == expected


def test_overlapping_writer_can_retry_after_first_finishes(tmp_path: Path) -> None:
    names = ["baseline.json"]
    with staged_outputs(tmp_path, names) as stage:
        (stage / names[0]).write_text("first")
        with pytest.raises(OSError, match="busy"), staged_outputs(tmp_path, names):
            pytest.fail("A second writer entered the same directory")
    with staged_outputs(tmp_path, names) as stage:
        (stage / names[0]).write_text("second")
    assert (tmp_path / names[0]).read_text() == "second"


@pytest.mark.parametrize(
    ("phase", "name", "had_outputs"),
    [
        ("backup", "index.json", True),
        ("backup", "001.step", True),
        ("install", "001.step", False),
        ("install", "index.json", True),
        ("install", "index.json", False),
    ],
)
def test_interrupt_after_rename_restores_complete_set(
    tmp_path: Path, phase: str, name: str, had_outputs: bool
) -> None:
    names = ["001.step", "index.json"]
    originals = {n: f"old {n}" for n in names} if had_outputs else {}
    for filename, content in originals.items():
        (tmp_path / filename).write_text(content)
    replace = Path.replace

    def interrupt_after_move(path: Path, target: Path) -> Path:
        if path.parent.name == "previous" and target.name == names[0]:
            assert not (tmp_path / names[-1]).exists()
        result = replace(path, target)
        if target.name == name and (
            (phase == "backup" and target.parent.name == "previous")
            or (phase == "install" and path.parent.name == "new")
        ):
            raise KeyboardInterrupt
        return result

    with (
        pytest.raises(KeyboardInterrupt),
        patch.object(Path, "replace", interrupt_after_move),
        staged_outputs(tmp_path, names) as stage,
    ):
        for filename in names:
            (stage / filename).write_text(f"new {filename}")
    assert {p.name: p.read_text() for p in tmp_path.iterdir()} == originals


@pytest.mark.parametrize("stop", [KeyboardInterrupt, PermissionError])
def test_interrupted_rollback_keeps_patch_and_report_backups(
    tmp_path: Path, stop: type[BaseException]
) -> None:
    names = ["review.patch", "review.patch.json"]
    for name in names:
        (tmp_path / name).write_text(f"old {name}")
    replace = Path.replace

    def interrupt_rollback(path: Path, target: Path) -> Path:
        if path.parent.name == "new" and target.name == names[-1]:
            raise PermissionError("report in use")
        if path.parent.name == "previous" and target.name == names[0]:
            raise stop("restore interrupted")
        return replace(path, target)

    with (
        pytest.raises(OSError if stop is PermissionError else stop) as failure,
        patch.object(Path, "replace", interrupt_rollback),
        staged_outputs(tmp_path, names) as stage,
    ):
        for name in names:
            (stage / name).write_text(f"new {name}")
    assert not (tmp_path / names[-1]).exists()
    previous = tmp_path / ".stepik-author-write" / "previous"
    if stop is PermissionError:
        assert str(previous) in str(failure.value)
    assert {p.name: p.read_text() for p in previous.iterdir()} == {
        name: f"old {name}" for name in names
    }
