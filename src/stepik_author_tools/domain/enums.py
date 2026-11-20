"""Stable identifiers shared by Stepik blocks and machine-readable reports."""

from enum import StrEnum


class StepKind(StrEnum):
    """Block types that can be compiled and synchronized."""

    TEXT = "text"
    CHOICE = "choice"
    MATCHING = "matching"


class SemanticField(StrEnum):
    """Independently compared parts of a supported step."""

    KIND = "kind"
    BODY = "body"
    OPTIONS = "options"
    ANSWERS = "answers"
    PAIRS = "pairs"
    SETTINGS = "settings"
    FEEDBACK = "feedback"


class StructureField(StrEnum):
    """Step relationships, identity and source layout used in reports."""

    POSITION = "position"
    LESSON = "lesson"
    MISSING = "missing"
    ADDED = "added"
    IDENTITY = "identity"
    ORDER = "order"
    PATHS = "paths"
    SOURCE = "source"
