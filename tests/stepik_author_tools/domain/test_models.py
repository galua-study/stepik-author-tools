"""Boundary and behavior contracts for domain/test_models.py."""

import pytest
from pydantic import ValidationError

from stepik_author_tools.domain.models import Block, Change, ChoiceOption, Manifest, StepSource


@pytest.mark.parametrize(
    "value",
    [
        {"version": 1, "topics": "bad"},
        {"version": 1, "topics": [{"id": "topic", "steps": [{"id": "step"}]}]},
        {"version": 1, "topics": [{"id": "topic", "lesson_id": True, "steps": []}]},
        {"version": True, "topics": []},
        {"version": "1", "topics": []},
        {"version": 2, "topics": []},
        {"version": 1, "topics": [], "typo": "value"},
    ],
)
def test_invalid_manifests_fail_at_the_boundary(value: object) -> None:
    with pytest.raises(ValueError):
        Manifest.model_validate(value)


@pytest.mark.parametrize("key", [None, 1, "true", "false"])
def test_choice_keys_are_strict_booleans(key: object) -> None:
    with pytest.raises(ValidationError, match="is_correct"):
        ChoiceOption.model_validate({"text": "An option", "is_correct": key})


def test_nested_missing_key_is_rejected_without_echoing_content() -> None:
    with pytest.raises(ValidationError) as caught:
        Block.model_validate(
            {
                "name": "choice",
                "text": "A question",
                "source": {"options": [{"text": "private-answer-text"}]},
            }
        )
    assert caught.value.errors()[0]["loc"] == ("source", "options", 0, "is_correct")
    assert "private-answer-text" not in str(caught.value)


def test_output_records_cannot_be_reassigned() -> None:
    change = Change(
        step_id="sample", position=1, field="answers", before=[1], after=[2], message="Changed"
    )
    with pytest.raises(ValidationError, match="frozen"):
        change.__setattr__("field", "body")


def test_source_defaults_are_independent_and_omissions_are_preserved() -> None:
    first, second = StepSource(), StepSource()
    first.options.append(ChoiceOption(text="A", is_correct=True))
    assert second.options == []
    assert second.to_dict(exclude_unset=True) == {}
    explicit = StepSource(preserve_order=False)
    assert explicit.to_dict(exclude_unset=True) == {"preserve_order": False}


def test_assignment_updates_wire_fields_and_revalidates_types() -> None:
    source = StepSource()
    source.preserve_order = True
    assert source.to_dict(exclude_unset=True) == {"preserve_order": True}
    with pytest.raises(ValidationError, match="sample_size"):
        source.sample_size = -1


def test_extensions_accept_json_but_reject_arbitrary_objects() -> None:
    with pytest.raises(ValidationError):
        StepSource.model_validate({"future_setting": object()})


def test_contracts_expose_json_schema_for_future_adapters() -> None:
    schema = Manifest.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["version", "topics"]
    assert "StepSpec" in schema["$defs"]
