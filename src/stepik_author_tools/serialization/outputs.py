"""Stage sibling outputs and roll back failed replacements."""

import os
import shutil
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path


def _prepare_replacements(directory: Path, staged: Path, names: Sequence[str]) -> None:
    for name in names:
        if not (staged / name).is_file():
            raise ValueError(f"Missing staged output: {name}")
        target = directory / name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError(f"Expected a regular output file: {target}")
        if target.exists():
            if os.name == "nt" and not os.access(target, os.W_OK):
                raise PermissionError(f"Read-only output: {target}")
            shutil.copymode(target, staged / name)


def _publish_batch(directory: Path, staged: Path, previous: Path, names: Sequence[str]) -> None:
    # Withdraw the old index/report first and publish the new one last
    for name in reversed(names):
        target = directory / name
        if target.exists():
            target.replace(previous / name)
    for name in names:
        (staged / name).replace(directory / name)


def _rollback(directory: Path, staged: Path, previous: Path, names: Sequence[str]) -> None:
    # Every file was staged before publication. A missing staged file was installed,
    # even if an interrupt arrived immediately after the rename
    for name in reversed(names):
        if not (staged / name).exists():
            (directory / name).unlink(missing_ok=True)
    for name in names:
        backup = previous / name
        if backup.exists():
            backup.replace(directory / name)


@contextmanager
def staged_outputs(directory: Path, names: Sequence[str]) -> Iterator[Path]:
    """Yield a private staging directory. Publish the last named artifact last."""
    directory.mkdir(parents=True, exist_ok=True)
    work = directory / ".stepik-author-write"
    staged, previous = work / "new", work / "previous"
    if any(directory / name == work for name in names):
        raise ValueError(f"Reserved output name: {work.name}")
    try:
        work.mkdir(mode=0o700)
    except FileExistsError:
        raise OSError(
            "Output busy or interrupted. Wait for any active writer to finish. "
            f"If {work} remains, keep the output directory and its backups in {previous}, "
            "then retry in a fresh output directory."
        ) from None
    try:
        previous.mkdir()
        staged.mkdir()
        yield staged
        _prepare_replacements(directory, staged, names)
        if len(names) == 1:
            (staged / names[0]).replace(directory / names[0])
    except BaseException:
        shutil.rmtree(work)
        raise

    if len(names) > 1:
        try:
            _publish_batch(directory, staged, previous, names)
        except BaseException:
            # If rollback itself fails, leave the remaining backups and the lock in place
            try:
                _rollback(directory, staged, previous, names)
            except OSError as error:
                raise OSError(
                    f"Could not restore outputs. Keep backups in {previous}: {error}"
                ) from error
            shutil.rmtree(work)
            raise
    shutil.rmtree(work)
