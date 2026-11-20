"""Boundary and behavior contracts for sync/test_semantic.py."""

import pytest

from stepik_author_tools.domain.enums import StepKind
from stepik_author_tools.domain.models import Block
from stepik_author_tools.sync.semantic import semantic_block


def test_unknown_source_settings_remain_visible_to_comparison() -> None:
    block = Block.model_validate(
        {"name": "text", "text": "hello", "source": {"future_setting": {"enabled": True}}}
    )
    semantic = semantic_block(block)
    assert semantic.kind is StepKind.TEXT
    assert semantic.to_dict()["settings"] == {"future_setting": {"enabled": True}}


def test_unsupported_wire_block_is_rejected_when_selected() -> None:
    block = Block(name="video", text="Demo")
    with pytest.raises(ValueError, match="Unsupported Stepik block: video"):
        semantic_block(block)
