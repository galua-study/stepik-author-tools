"""Load source projects, validate identities and compile selected course materials."""

from dataclasses import dataclass, field
from pathlib import Path

from ..config import Settings, load_settings
from ..domain.models import Manifest, StepRecord, StepSpec, TopicSpec
from ..markdown.material import Material
from ..serialization.files import read_text
from .legacy import load_legacy
from .manifests import find_manifest


@dataclass
class Course:
    """A source root and its identity manifest; compilation never edits either."""

    root: Path
    manifest: Manifest
    manifest_path: Path | None = None
    settings: Settings = field(default_factory=load_settings)

    def input_paths(self) -> list[Path]:
        """List all owned sources and maps, including sources outside the selected scope."""
        paths = [
            self.source_path(path)
            for topic in self.manifest.topics
            for step in topic.steps
            for path in step.source_paths()
        ]
        if self.manifest_path is not None:
            paths.append(self.manifest_path)
        else:
            paths.extend(self.root.glob("README.md"))
            paths.extend(self.root.glob("*/README.md"))
        return paths

    def source_path(self, relative: str) -> Path:
        """Resolve a Markdown path inside the course, including symlink resolution."""
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"Source escapes project root: {relative}")
        return path

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
        texts = [read_text(self.source_path(path)) for path in paths]
        dialect = self.settings.markdown
        if len(paths) > 1 and any(Material(text, dialect).task for text in texts):
            raise ValueError("Only text lessons may combine multiple source files")
        try:
            block = Material("\n\n".join(texts), dialect).compile()
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
                path = course.source_path(relative)
                if path in paths:
                    raise ValueError("Each source file must belong to exactly one step")
                paths.add(path)


def load_course(path: str | Path, *, settings: Settings | None = None) -> Course:
    """Read a manifest or legacy map, enforcing path containment and unique identities."""
    path = Path(path).resolve()
    settings = settings or load_settings()
    manifest_path = find_manifest(path, settings.project.manifest_name)
    if manifest_path is not None:
        manifest = Manifest.model_validate_json(read_text(manifest_path))
        course = Course(manifest_path.parent, manifest, manifest_path, settings)
    else:
        root, manifest = load_legacy(path.parent if path.is_file() else path, settings.maps)
        course = Course(root, manifest, settings=settings)
    _validate_identities(course)
    return course
