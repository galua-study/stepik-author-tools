"""Read-only adapter from ordered Russian topic maps to an explicit manifest."""

import hashlib
from itertools import groupby
from pathlib import Path

from ..config.authoring import MapSettings
from ..domain.models import Manifest, StepSpec, TopicSpec
from ..serialization.files import read_text


def _topic_order(path: Path) -> list[tuple[int, int | str]]:
    # Topic 2 must precede Topic 10; string sorting would change the course sequence.
    return [
        (0, int("".join(chars))) if digits else (1, "".join(chars).casefold())
        for digits, chars in groupby(path.parent.name, key=str.isdecimal)
    ]


def _map_step(root: Path, map_path: Path, number: str, cell: str, rules: MapSettings) -> StepSpec:
    links = [match["path"] for match in rules.link.finditer(cell)]
    if not links:
        raise ValueError(f"Unrecognized map link in {map_path.name}, row {number}")
    paths = []
    for link in links:
        resolved = (map_path.parent / link).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("Map source escapes module root")
        paths.append(resolved.relative_to(root).as_posix())
    stable_id = hashlib.sha256("|".join(paths).encode()).hexdigest()[:16]
    return StepSpec(id=stable_id, paths=paths)


def _map_topic(root: Path, map_path: Path, rules: MapSettings) -> TopicSpec | None:
    text = read_text(map_path)
    rows = list(rules.row.finditer(text))
    if not rows:
        return None
    if [int(row["number"]) for row in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("Map positions must be consecutive")
    lesson = rules.lesson.search(text)
    return TopicSpec(
        id=map_path.parent.name,
        module=root.name,
        lesson_id=int(lesson["id"]) if lesson else None,
        steps=[_map_step(root, map_path, row["number"], row["cell"], rules) for row in rows],
    )


def load_legacy(directory: Path, rules: MapSettings) -> tuple[Path, Manifest]:
    """Load topic/module maps, allowing introductions in the parent module folder."""
    maps = [directory / "README.md"] if (directory / "README.md").exists() else []
    maps += sorted(directory.glob("*/README.md"), key=_topic_order)
    root = directory.parent if rules.topic_folder.match(directory.name) else directory
    topics = [
        topic for map_path in maps if (topic := _map_topic(root, map_path, rules)) is not None
    ]
    if not topics:
        raise ValueError("No course manifest or ordered topic README maps found")
    return root, Manifest(version=1, topics=topics)
