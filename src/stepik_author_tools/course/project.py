"""Load source projects, validate identities and compile selected course materials."""

from dataclasses import dataclass
from pathlib import Path

from ..domain.models import Manifest, StepRecord, StepSpec, TopicSpec
from ..markdown.material import Material
from ..serialization.jsonio import contained, load_json, read
from .legacy import load_legacy


@dataclass
class Course:
    """A source root and its identity manifest; compilation never edits either."""

    root: Path
    manifest: Manifest
    manifest_path: Path | None = None

    def topics(self, scope: str | None = None) -> list[TopicSpec]:
        """Select all topics, an exact topic ID, or an exact module ID."""
        topics = [
            topic
            for topic in self.manifest.topics
            if scope is None or scope in (topic.id, topic.module)
        ]
        if not topics:
            raise ValueError(f"Unknown or empty scope: {scope}")
        return topics

    def _compile_step(self, topic: TopicSpec, step: StepSpec, position: int) -> StepRecord:
        paths = step.source_paths()
        texts = [read(contained(self.root, path)) for path in paths]
        if len(paths) > 1 and any(Material(text).task for text in texts):
            raise ValueError("Only text lessons may combine multiple source files")
        try:
            block = Material("\n\n".join(texts)).compile()
        except ValueError as error:
            raise ValueError(f"{paths[0]}: {error}") from error
        return StepRecord(
            id=step.id,
            stepik_id=step.stepik_id,
            topic=topic.id,
            lesson=topic.lesson_id,
            position=position,
            paths=paths,
            block=block,
        )

    def compile(self, scope: str | None = None) -> list[StepRecord]:
        """Compile sources in manifest order with stable IDs alongside their positions."""
        return [
            self._compile_step(topic, step, position)
            for topic in self.topics(scope)
            for position, step in enumerate(topic.steps, 1)
        ]


def _check_unique(value: str | int, seen: set[str | int], label: str) -> None:
    if value in seen:
        raise ValueError(f"Duplicate {label}")
    seen.add(value)


def _validate_identities(course: Course) -> None:
    local_ids: set[str | int] = set()
    remote_ids: set[str | int] = set()
    topic_ids: set[str | int] = set()
    lesson_ids: set[str | int] = set()
    paths: set[Path] = set()
    for topic in course.manifest.topics:
        _check_unique(topic.id, topic_ids, "topic ID")
        if (lesson_id := topic.lesson_id) is not None:
            _check_unique(lesson_id, lesson_ids, "lesson ID")
        for step in topic.steps:
            _check_unique(step.id, local_ids, "step ID")
            if (remote_id := step.stepik_id) is not None:
                _check_unique(remote_id, remote_ids, "Stepik ID")
            for relative in step.source_paths():
                path = contained(course.root, relative)
                if path in paths:
                    raise ValueError("Each source file must belong to exactly one step")
                paths.add(path)


def load_course(path: str | Path) -> Course:
    """Read a manifest or legacy map, enforcing path containment and unique identities."""
    path = Path(path).resolve()
    if path.is_dir() and (path / "course.json").exists():
        path /= "course.json"
    if path.suffix == ".json":
        course = Course(path.parent, Manifest.model_validate(load_json(path)), path)
    else:
        root, manifest = load_legacy(path.parent if path.is_file() else path)
        course = Course(root, manifest)
    _validate_identities(course)
    return course
