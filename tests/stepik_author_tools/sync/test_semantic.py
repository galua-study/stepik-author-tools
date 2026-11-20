"""Boundary and behavior contracts for sync/test_semantic.py."""

from stepik_author_tools.domain.models import Block
from stepik_author_tools.sync.semantic import semantic_block


def test_unknown_source_settings_remain_visible_to_comparison() -> None:
    block = Block.model_validate(
        {"name": "text", "text": "hello", "source": {"future_setting": {"enabled": True}}}
    )
    assert semantic_block(block).to_dict()["settings"] == {"future_setting": {"enabled": True}}
