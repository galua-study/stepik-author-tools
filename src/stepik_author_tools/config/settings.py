"""Load a validated settings object for one course or HTTP client."""

import tomllib
from functools import cache
from importlib.resources import files
from pathlib import Path, PureWindowsPath
from typing import Annotated

from pydantic import Field, HttpUrl, field_validator

from ..domain.enums import SemanticField
from ..domain.models import NonEmptyText
from ..serialization.files import JSON_SUFFIX, read_text
from .authoring import MapSettings, MarkdownSettings
from .validation import ConfigModel


class ApiSettings(ConfigModel):
    """Network boundary for GET requests, including its allowlist and pagination cap."""

    base_url: HttpUrl
    resources: Annotated[frozenset[str], Field(min_length=1)]
    max_pages: Annotated[int, Field(gt=0, strict=True)]
    timeout: Annotated[float, Field(gt=0, strict=True, allow_inf_nan=False)]

    @field_validator("base_url")
    @classmethod
    def https_endpoint(cls, url: HttpUrl) -> HttpUrl:
        """Only an HTTPS base path can be joined with resource names."""
        if url.scheme != "https" or any((url.username, url.password, url.query, url.fragment)):
            raise ValueError("Expected an HTTPS base URL without credentials, query or fragment")
        return url

    @field_validator("resources")
    @classmethod
    def literal_resource_names(cls, names: frozenset[str]) -> frozenset[str]:
        """Each allowed resource must be a single path segment."""
        for name in names:
            if not name.isascii() or not all(part.isalnum() for part in name.split("-")):
                raise ValueError("Expected a resource name made of letters, digits and hyphens")
        return names


class ProjectSettings(ConfigModel):
    """Preferred manifest filename for directory-based discovery."""

    manifest_name: str

    @field_validator("manifest_name")
    @classmethod
    def json_filename(cls, value: str) -> str:
        """The preferred filename belongs in the given course directory on every OS."""
        path = PureWindowsPath(value)
        if path.name != value or path.suffix.casefold() != JSON_SUFFIX:
            raise ValueError("manifest_name must be a JSON filename without a directory")
        return value


class DiffLabels(ConfigModel):
    """Human-readable messages keyed by stable fields used in JSON reports."""

    fields: dict[SemanticField, NonEmptyText]
    code: NonEmptyText
    moved: NonEmptyText
    missing: NonEmptyText
    added: NonEmptyText

    @field_validator("fields")
    @classmethod
    def complete(cls, labels: dict[SemanticField, str]) -> dict[SemanticField, str]:
        """A missing label would otherwise fail only when that field changed."""
        if missing := set(SemanticField) - labels.keys():
            raise ValueError(f"Missing comparison labels: {', '.join(sorted(missing))}")
        return labels


class Settings(ConfigModel):
    """All settings for one invocation, independent of the current working directory."""

    api: ApiSettings
    project: ProjectSettings
    markdown: MarkdownSettings
    maps: MapSettings
    diff: DiffLabels


@cache
def _defaults() -> dict[str, object]:
    with files(__package__).joinpath("defaults.toml").open("rb") as stream:
        return tomllib.load(stream)


def _overlay(
    defaults: dict[str, object], overrides: dict[str, object], table: tuple[str, ...] = ()
) -> dict[str, object]:
    """Merge tables and extend heading aliases so existing answer keys stay private."""
    result = defaults.copy()
    for key, value in overrides.items():
        old = defaults.get(key)
        location = (*table, key)
        if isinstance(old, dict) and isinstance(value, dict):
            result[key] = _overlay(old, value, location)
        elif (
            isinstance(old, list)
            and isinstance(value, list)
            and (table == ("markdown", "author_sections") or location == ("markdown", "condition"))
        ):
            result[key] = [*old, *(item for item in value if item not in old)]
        else:
            result[key] = value
    return result


def load_settings(path: str | Path | None = None) -> Settings:
    """Read packaged defaults and apply only the entries in an explicitly selected TOML file."""
    values = _defaults()
    if path is not None:
        values = _overlay(values, tomllib.loads(read_text(Path(path))))
    return Settings.model_validate(values)
