"""Read-only adapter from ordered Russian topic maps to an explicit manifest."""

import hashlib
import re
from pathlib import Path

from ..domain.models import Manifest, StepSpec, TopicSpec
from ..serialization.jsonio import read


def _topic_order(path: Path) -> list[tuple[int, int | str]]:
    # Topic 2 must precede Topic 10; string sorting would change the course sequence.
    return [
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", path.parent.name)
    ]


def _map_step(root: Path, map_path: Path, number: str, cell: str) -> StepSpec:
    links = re.findall(r"\]\(<([^>]+)>\)", cell)
    if not links:
        raise ValueError(f"Unrecognized map link in {map_path.name}, row {number}")
    paths = []
    for link in links:
        resolved = (map_path.parent / link).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("Map source escapes module root")
        paths.append(resolved.relative_to(root).as_posix())
    stable_id = hashlib.sha256("|".join(paths).encode()).hexdigest()[:16]
    return {"id": stable_id, "paths": paths}


def _map_topic(root: Path, map_path: Path) -> TopicSpec | None:
    text = read(map_path)
    rows = re.findall(r"(?m)^\|\s*(\d+)\s*\|(.+?)\|", text)
    if not rows:
        return None
    if [int(number) for number, _ in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("Map positions must be consecutive")
    lesson = re.search(r"stepik.org/(?:edit-)?lesson/(\d+)", text)
    return {
        "id": map_path.parent.name,
        "module": root.name,
        "lesson_id": int(lesson[1]) if lesson else None,
        "steps": [_map_step(root, map_path, number, cell) for number, cell in rows],
    }


def load_legacy(directory: Path) -> tuple[Path, Manifest]:
    """Load topic/module maps, allowing introductions in the parent module folder."""
    maps = [directory / "README.md"] if (directory / "README.md").exists() else []
    maps += sorted(directory.glob("*/README.md"), key=_topic_order)
    root = directory.parent if re.match(r"Тема\s", directory.name) else directory
    topics = [topic for map_path in maps if (topic := _map_topic(root, map_path)) is not None]
    if not topics:
        raise ValueError("No course.json or ordered topic README maps found")
    return root, {"version": 1, "topics": topics}
