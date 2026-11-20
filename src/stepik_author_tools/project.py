"""Explicit identity manifests and a read-only adapter for Russian topic maps."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from .material import Material


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def contained(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Source escapes project root: {relative}")
    return path


@dataclass
class Course:
    root: Path
    manifest: dict
    manifest_path: Path | None = None

    def topics(self, scope: str | None = None) -> list[dict]:
        topics = [t for t in self.manifest["topics"] if scope is None or scope in (t["id"], t.get("module"))]
        if not topics:
            raise ValueError(f"Unknown or empty scope: {scope}")
        return topics

    def compile(self, scope: str | None = None) -> list[dict]:
        result = []
        for topic in self.topics(scope):
            for position, step in enumerate(topic["steps"], 1):
                paths = step.get("paths") or [step["path"]]
                texts = [read(contained(self.root, p)) for p in paths]
                materials = [Material(text) for text in texts]
                if len(paths) > 1 and any(m.task for m in materials):
                    raise ValueError("Only text lessons may combine multiple source files")
                try:
                    block = Material("\n\n".join(texts)).compile()
                except ValueError as error:
                    raise ValueError(f"{paths[0]}: {error}") from error
                result.append(dict(id=step["id"], stepik_id=step.get("stepik_id"), topic=topic["id"],
                                   lesson=topic.get("lesson_id"), position=position, paths=paths, block=block))
        return result


def load_course(path: str | Path) -> Course:
    path = Path(path).resolve()
    if path.is_dir() and (path / "course.json").exists():
        path /= "course.json"
    if path.suffix == ".json":
        data = json.loads(read(path))
        if data.get("version") != 1:
            raise ValueError("Expected manifest version 1")
        course = Course(path.parent, data, path)
    else:
        directory = path.parent if path.is_file() else path
        maps = [directory / "README.md"] if (directory / "README.md").exists() else []
        # Topic 2 precedes Topic 10 when a legacy module has no manifest.
        maps += sorted(directory.glob("*/README.md"), key=lambda p: [
            (0, int(part)) if part.isdigit() else (1, part.casefold())
            for part in re.split(r"(\d+)", p.parent.name)
        ])
        topics = []
        # Root allows a topic introduction composed from parent module files.
        root = directory.parent if re.match(r"Тема\s", directory.name) else directory
        for map_path in maps:
            text = read(map_path)
            rows = re.findall(r"(?m)^\|\s*(\d+)\s*\|(.+?)\|", text)
            if not rows:
                continue
            steps = []
            for number, cell in rows:
                paths = re.findall(r"\]\(<([^>]+)>\)", cell)
                if not paths:
                    raise ValueError(f"Unrecognized map link in {map_path.name}, row {number}")
                relatives = []
                for value in paths:
                    resolved = (map_path.parent / value).resolve()
                    if not resolved.is_relative_to(root):
                        raise ValueError("Map source escapes module root")
                    relatives.append(resolved.relative_to(root).as_posix())
                stable = hashlib.sha256("|".join(relatives).encode()).hexdigest()[:16]
                steps.append(dict(id=stable, paths=relatives))
            if [int(n) for n, _ in rows] != list(range(1, len(rows)+1)):
                raise ValueError("Map positions must be consecutive")
            lesson = re.search(r"stepik.org/(?:edit-)?lesson/(\d+)", text)
            topics.append(dict(id=map_path.parent.name, module=root.name,
                               lesson_id=int(lesson[1]) if lesson else None, steps=steps))
        if not topics:
            raise ValueError("No course.json or ordered topic README maps found")
        course = Course(root, dict(version=1, topics=topics))
    ids, remote_ids, paths, topic_ids, lesson_ids = set(), set(), set(), set(), set()
    for topic in course.manifest["topics"]:
        if topic["id"] in topic_ids:
            raise ValueError("Duplicate topic ID")
        topic_ids.add(topic["id"])
        lesson = topic.get("lesson_id")
        if lesson is not None:
            if not isinstance(lesson, int) or lesson <= 0 or lesson in lesson_ids:
                raise ValueError("Lesson IDs must be unique positive integers")
            lesson_ids.add(lesson)
        for step in topic["steps"]:
            if not isinstance(step["id"], str) or not step["id"] or step["id"] in ids:
                raise ValueError("Step IDs must be unique nonempty strings")
            ids.add(step["id"])
            rid = step.get("stepik_id")
            if rid is not None:
                if not isinstance(rid, int) or rid <= 0 or rid in remote_ids:
                    raise ValueError("Stepik IDs must be unique positive integers")
                remote_ids.add(rid)
            for p in step.get("paths") or [step["path"]]:
                resolved = contained(course.root, p)
                if resolved in paths:
                    raise ValueError("Each source file must belong to exactly one step")
                paths.add(resolved)
    return course
