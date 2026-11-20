"""JSON and filesystem boundaries with explicit runtime type checks."""

import json
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from ..domain.models import JsonObject, JsonValue


def json_value(value: object) -> JsonValue:
    """Copy a serializable value, rejecting non-string keys and unknown objects."""
    if isinstance(value, BaseModel):
        return json_value(value.model_dump(mode="json", exclude_unset=True))
    if value is None or isinstance(value, str | bool | int | float):
        return value
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, Mapping):
        result: JsonObject = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            result[key] = json_value(item)
        return result
    raise ValueError(f"Not a JSON value: {type(value).__name__}")


def object_value(value: object, label: str = "value") -> JsonObject:
    """Require a JSON object at an external input boundary."""
    result = json_value(value)
    if not isinstance(result, dict):
        raise ValueError(f"Expected {label} to be an object")
    return result


def array_value(value: object, label: str) -> list[JsonValue]:
    """Require an array rather than accepting strings or arbitrary iterables."""
    if not isinstance(value, list):
        raise ValueError(f"Expected {label} to be an array")
    return [json_value(item) for item in value]


def read(path: Path) -> str:
    """Read UTF-8 Markdown/JSON, accepting a Windows UTF-8 BOM."""
    return path.read_text(encoding="utf-8-sig")


def load_json(path: Path) -> JsonObject:
    """Read and validate a JSON object without leaking an untyped decoder result."""
    return object_value(json.loads(read(path)))


def write_json(path: Path, value: object) -> None:
    """Write deterministic UTF-8 JSON with LF endings on every platform."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_value(value), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def contained(root: Path, relative: str) -> Path:
    """Resolve a source path and reject traversal and symlinks outside the root."""
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Source escapes project root: {relative}")
    return path
