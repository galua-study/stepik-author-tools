"""Validated Pydantic contracts for author sources and synchronization results."""

from typing import TYPE_CHECKING, Annotated, Literal, Self, TypeAlias

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter, model_validator
from pydantic import JsonValue as JsonValue

from .enums import SemanticField, StepKind, StructureField

JsonObject: TypeAlias = dict[str, JsonValue]
# Strict models also accept these exact enum values in already-decoded JSON objects.
ReportField: TypeAlias = (
    Annotated[SemanticField, BeforeValidator(lambda value: SemanticField(value))]
    | Annotated[StructureField, BeforeValidator(lambda value: StructureField(value))]
)
PositiveId: TypeAlias = Annotated[int, Field(gt=0)]
NonEmptyText: TypeAlias = Annotated[str, Field(min_length=1)]
Version: TypeAlias = Annotated[int, Field(ge=1, le=1)]
_JSON_OBJECT = TypeAdapter(JsonObject)


class DomainModel(BaseModel):
    """Strict input types, explicit fields and errors that do not echo source content."""

    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        validate_assignment=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
    )

    def to_dict(self, *, exclude_unset: bool = False) -> JsonObject:
        """Serialize to JSON values, optionally preserving omitted source fields."""
        return _JSON_OBJECT.validate_python(
            self.model_dump(mode="json", exclude_unset=exclude_unset),
            strict=True,
        )


class ExtensibleModel(DomainModel):
    """Retain JSON extension fields from Stepik instead of hiding unknown settings."""

    model_config = ConfigDict(extra="allow")
    # Pydantic reads this runtime annotation to validate extra values. Its base
    # class already declares the storage as an internal, non-constructor attribute.
    if not TYPE_CHECKING:
        __pydantic_extra__: JsonObject


class ChoiceOption(ExtensibleModel):
    """Author-visible choice option with an explicit, strictly boolean answer key."""

    text: str
    is_correct: bool
    feedback: str = ""


class MatchingPair(ExtensibleModel):
    """Rendered fragments belonging to one correct matching pair."""

    first: str
    second: str


class StepSource(ExtensibleModel):
    """Known grading settings; only fields actually supplied are compared/exported."""

    options: list[ChoiceOption] = Field(default_factory=list)
    pairs: list[MatchingPair] = Field(default_factory=list)
    is_multiple_choice: bool = False
    is_always_correct: bool = False
    sample_size: int = Field(default=0, ge=0)
    preserve_order: bool = False
    is_html_enabled: bool = False
    is_options_feedback: bool = False
    preserve_firsts_order: bool = False


class Block(ExtensibleModel):
    """Stepik content plus author settings, retaining optional editor metadata."""

    name: str
    text: str
    source: StepSource | None = None
    options: JsonObject = Field(default_factory=dict)
    is_deprecated: bool = False
    video: JsonValue = None
    subtitles: JsonObject = Field(default_factory=dict)
    subtitle_files: list[JsonValue] = Field(default_factory=list)
    tests_archive: JsonValue = None
    feedback_correct: str = ""
    feedback_wrong: str = ""


class StepRecord(DomainModel):
    """Snapshot row; local compilation additionally supplies identity and source paths."""

    stepik_id: PositiveId | None = None
    lesson: PositiveId | None = None
    position: PositiveId
    block: Block
    id: str = ""
    topic: str = ""
    paths: list[str] = Field(default_factory=list)


class Snapshot(DomainModel):
    """Complete selected lessons, optionally marked as a verified common ancestor."""

    version: Version
    steps: list[StepRecord]
    kind: Literal["verified-baseline"] | None = None


class StepSpec(DomainModel):
    """Stable local identity and either a path or ordered combined source paths."""

    id: NonEmptyText
    stepik_id: PositiveId | None = None
    path: NonEmptyText | None = None
    paths: list[NonEmptyText] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_source(self) -> Self:
        """Require source material rather than postponing a missing-key error until build."""
        if not self.path and not self.paths:
            raise ValueError("Each step requires path or nonempty paths")
        return self

    def source_paths(self) -> list[str]:
        """Return source order, preserving the existing preference for combined paths."""
        if self.paths:
            return self.paths
        assert self.path is not None
        return [self.path]


class TopicSpec(DomainModel):
    """Ordered lesson manifest and its module membership."""

    id: NonEmptyText
    steps: list[StepSpec]
    module: str | None = None
    lesson_id: PositiveId | None = None


class Manifest(DomainModel):
    """Versioned course source manifest, independent of CLI and HTTP transport."""

    version: Version
    topics: list[TopicSpec]
    title: str | None = None


class Conflict(DomainModel):
    """Three-way evidence for one conflict without embedding markers in source files."""

    model_config = ConfigDict(frozen=True)
    step_id: str
    field: ReportField
    reason: str = ""
    base: JsonValue = None
    local: JsonValue = None
    remote: JsonValue = None


class SemanticStep(DomainModel):
    """Normalized content and grading state without transport/editor metadata."""

    model_config = ConfigDict(frozen=True)
    kind: Annotated[StepKind, BeforeValidator(lambda value: StepKind(value))]
    body: str
    options: tuple[str, ...] = ()
    answers: tuple[int, ...] = ()
    pairs: tuple[tuple[str, str], ...] = ()
    settings: JsonObject = Field(default_factory=dict)
    feedback: tuple[str, ...] = ()


class Change(DomainModel):
    """One semantic or structural difference and its readable detail."""

    model_config = ConfigDict(frozen=True)
    step_id: str
    position: PositiveId
    field: ReportField
    before: JsonValue
    after: JsonValue
    message: str
    detail: str = ""


class PullResult(DomainModel):
    """Patch proposal only; producing a result never changes course source files."""

    model_config = ConfigDict(frozen=True)
    patch: str
    conflicts: list[Conflict]
    changed_files: list[str]
