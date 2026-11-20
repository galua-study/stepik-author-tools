"""Stepik response envelopes, separate from the application's snapshot format."""

from pydantic import ConfigDict, Field

from .models import Block, DomainModel, PositiveId, Snapshot, StepRecord


class PageMetadata(DomainModel):
    """Pagination flag with strict boolean validation; other API metadata is ignored."""

    model_config = ConfigDict(extra="ignore")
    has_next: bool = False


class LessonSteps(DomainModel):
    """Ordered positive step IDs from a lesson response."""

    model_config = ConfigDict(extra="ignore")
    steps: list[PositiveId]


class AuthorStep(DomainModel):
    """Author API row; unrelated platform metadata does not enter local snapshots."""

    model_config = ConfigDict(extra="ignore")
    id: PositiveId
    lesson: PositiveId
    position: PositiveId
    block: Block

    def to_record(self) -> StepRecord:
        """Translate platform identity to the explicit snapshot stepik_id field."""
        return StepRecord(
            stepik_id=self.id, lesson=self.lesson, position=self.position, block=self.block
        )


class AuthorSteps(DomainModel):
    """Complete step-sources envelope, including optional pagination metadata."""

    model_config = ConfigDict(extra="ignore")
    steps: list[AuthorStep] = Field(alias="step-sources")

    def to_snapshot(self) -> Snapshot:
        """Convert validated author rows without guessing local IDs or source paths."""
        return Snapshot(version=1, steps=[step.to_record() for step in self.steps])
