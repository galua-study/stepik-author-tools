"""Validation of the public and author API response envelopes."""

import pytest
from pydantic import ValidationError

from stepik_author_tools.domain.stepik import LessonSteps, PageMetadata


@pytest.mark.parametrize("step_id", [True, 0, -1, "2"])
def test_lesson_ids_reject_coercion_and_nonpositive_values(step_id: object) -> None:
    with pytest.raises(ValidationError):
        LessonSteps.model_validate({"steps": [step_id]})


def test_unrelated_pagination_metadata_is_ignored() -> None:
    page = PageMetadata.model_validate({"page": 2, "has_next": False, "has_previous": True})
    assert not page.has_next
