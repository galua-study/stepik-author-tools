"""UTF-8 course files and the two snapshot formats accepted by the CLI and library."""

import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import ConfigDict, TypeAdapter

from ..domain.models import JsonValue, Snapshot
from ..domain.stepik import AuthorSteps

JSON_SUFFIX = ".json"
_SNAPSHOT = TypeAdapter(Snapshot | AuthorSteps, config=ConfigDict(hide_input_in_errors=True))


def read_text(path: Path) -> str:
    """Accept Markdown and JSON saved with a Windows UTF-8 BOM."""
    return path.read_text(encoding="utf-8-sig")


def write_json(path: Path, value: JsonValue) -> None:
    """Write an already serialized value with stable indentation, Unicode and LF endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8", newline="\n")


def protect_inputs(outputs: Iterable[Path], inputs: Iterable[Path]) -> None:
    """Reject output aliases of inputs before writing any artifact in a batch."""
    protected = [path.resolve() for path in inputs]
    for output in outputs:
        resolved = output.resolve()
        if any(
            resolved == path or (resolved.exists() and path.exists() and resolved.samefile(path))
            for path in protected
        ):
            raise ValueError(f"Output would overwrite an input file: {output}")


def read_snapshot(path: str | Path) -> Snapshot:
    """Validate an offline snapshot or translate the IDs in a Stepik author export."""
    data = _SNAPSHOT.validate_json(read_text(Path(path)))
    return data.to_snapshot() if isinstance(data, AuthorSteps) else data
