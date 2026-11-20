"""Discover a course manifest among snapshots, baselines and other project files."""

import json
from pathlib import Path

from ..serialization.files import JSON_SUFFIX, read_text


def _looks_like_manifest(path: Path) -> bool:
    try:
        data = json.loads(read_text(path))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and "topics" in data and "version" in data


def find_manifest(path: Path, preferred_name: str) -> Path | None:
    """Prefer an explicit file, then the configured name, then one unambiguous manifest."""
    if path.is_file():
        return path if path.suffix.casefold() == JSON_SUFFIX else None
    if not path.is_dir():
        raise FileNotFoundError(f"Course path does not exist: {path}")
    preferred = path / preferred_name
    if preferred.is_file():
        return preferred
    candidates = sorted(
        entry
        for entry in path.iterdir()
        if entry.is_file()
        and entry.suffix.casefold() == JSON_SUFFIX
        and _looks_like_manifest(entry)
    )
    if len(candidates) > 1:
        names = ", ".join(candidate.name for candidate in candidates)
        raise ValueError(f"Multiple course manifests ({names}); pass the intended file")
    return next(iter(candidates), None)
