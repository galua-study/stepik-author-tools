"""Validate untrusted JSON before it enters typed course and snapshot operations.

The casts below follow runtime validation of every declared field. Keeping the
original mappings also preserves unknown Stepik extension settings for comparison.
"""

from pathlib import Path
from typing import cast

from ..domain.models import Block, Manifest, Snapshot, StepRecord, StepSource, StepSpec, TopicSpec
from .jsonio import array_value, integer_value, load_json, object_value, optional_id, string_value

_BOOLEAN_SETTINGS = (
    "is_multiple_choice",
    "is_always_correct",
    "preserve_order",
    "is_html_enabled",
    "is_options_feedback",
    "preserve_firsts_order",
)


def _optional_strings(data: dict[str, object], keys: tuple[str, ...]) -> None:
    for key in keys:
        if key in data:
            string_value(data[key], key)


def parse_source(value: object) -> StepSource:
    """Validate known grading fields while retaining extension settings."""
    data = object_value(value, "block.source")
    for key in _BOOLEAN_SETTINGS:
        if key in data and not isinstance(data[key], bool):
            raise ValueError(f"Expected source.{key} to be a boolean")
    if "sample_size" in data:
        integer_value(data["sample_size"], "source.sample_size")
    if "options" in data:
        _validate_options(data["options"])
    if "pairs" in data:
        for item in array_value(data["pairs"], "source.pairs"):
            pair = object_value(item, "pair")
            string_value(pair.get("first"), "pair.first")
            string_value(pair.get("second"), "pair.second")
    return cast(StepSource, data)


def _validate_options(value: object) -> None:
    for item in array_value(value, "source.options"):
        option = object_value(item, "option")
        string_value(option.get("text"), "option.text")
        if "is_correct" in option and not isinstance(option["is_correct"], bool):
            raise ValueError("Choice source does not expose correct answers")
        if "feedback" in option:
            string_value(option["feedback"], "option.feedback")


def parse_block(value: object) -> Block:
    """Validate a block payload independently of its supported exercise kind."""
    data = object_value(value, "block")
    string_value(data.get("name"), "block.name")
    string_value(data.get("text"), "block.text")
    if data.get("source") is not None:
        parse_source(data["source"])
    _optional_strings(dict(data), ("feedback_correct", "feedback_wrong"))
    for key in ("options", "subtitles"):
        if key in data:
            object_value(data[key], f"block.{key}")
    if "subtitle_files" in data:
        array_value(data["subtitle_files"], "block.subtitle_files")
    if "is_deprecated" in data and not isinstance(data["is_deprecated"], bool):
        raise ValueError("Expected block.is_deprecated to be a boolean")
    return cast(Block, data)


def _parse_step(value: object, *, api: bool = False) -> StepRecord:
    data = object_value(value, "step")
    result: StepRecord = {
        "stepik_id": optional_id(data.get("id" if api else "stepik_id"), "stepik_id"),
        "lesson": optional_id(data.get("lesson"), "lesson"),
        "position": integer_value(data.get("position"), "position"),
        "block": parse_block(data.get("block")),
    }
    if not api:
        for key in ("id", "topic"):
            if key in data:
                result[key] = string_value(data[key], key)
        if "paths" in data:
            result["paths"] = [string_value(p, "path") for p in array_value(data["paths"], "paths")]
    return result


def normalize_snapshot(value: object) -> Snapshot:
    """Accept a complete version-1 snapshot or a Stepik step-sources envelope."""
    data = object_value(value, "snapshot")
    if "step-sources" in data:
        return {
            "version": 1,
            "steps": [
                _parse_step(row, api=True)
                for row in array_value(data["step-sources"], "step-sources")
            ],
        }
    if data.get("version") != 1:
        raise ValueError("Expected version 1 snapshot or Stepik step-sources response")
    result: Snapshot = {
        "version": 1,
        "steps": [_parse_step(row) for row in array_value(data.get("steps"), "steps")],
    }
    if "kind" in data:
        result["kind"] = string_value(data["kind"], "kind")
    return result


def source_paths(step: StepSpec) -> list[str]:
    """Return ordered source paths, rejecting absent or empty path definitions."""
    if paths := step.get("paths"):
        return paths
    if path := step.get("path"):
        return [path]
    raise ValueError("Each step requires path or nonempty paths")


def _validate_step_spec(value: object) -> None:
    data = object_value(value, "step specification")
    if not string_value(data.get("id"), "step.id"):
        raise ValueError("Step IDs must be unique nonempty strings")
    optional_id(data.get("stepik_id"), "stepik_id")
    if "path" in data:
        string_value(data["path"], "path")
    if "paths" in data:
        for path in array_value(data["paths"], "paths"):
            string_value(path, "path")
    source_paths(cast(StepSpec, data))


def parse_manifest(value: object) -> Manifest:
    """Validate manifest field types; cross-record identity checks live in project."""
    data = object_value(value, "manifest")
    if data.get("version") != 1:
        raise ValueError("Expected manifest version 1")
    if "title" in data:
        string_value(data["title"], "title")
    for item in array_value(data.get("topics"), "topics"):
        topic = object_value(item, "topic")
        string_value(topic.get("id"), "topic.id")
        optional_id(topic.get("lesson_id"), "lesson_id")
        if "module" in topic:
            string_value(topic["module"], "module")
        for step in array_value(topic.get("steps"), "steps"):
            _validate_step_spec(step)
    return cast(Manifest, data)


def selected_topics(manifest: Manifest, scope: str | None) -> list[TopicSpec]:
    """Select an exact topic/module ID and reject an unknown or empty scope."""
    topics = [
        topic
        for topic in manifest["topics"]
        if scope is None or scope in (topic["id"], topic.get("module"))
    ]
    if not topics:
        raise ValueError(f"Unknown or empty scope: {scope}")
    return topics


def read_snapshot(path: str | Path) -> Snapshot:
    """Read an offline snapshot through the same validation as live API data."""
    return normalize_snapshot(load_json(Path(path)))
