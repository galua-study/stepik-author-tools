"""Compatibility facade; operation implementations live in the sync package."""

from collections.abc import Mapping

from .domain.models import Change as Change
from .domain.models import JsonObject
from .domain.models import PullResult as PullResult
from .serialization.jsonio import write_json as write_json
from .serialization.schemas import parse_block
from .sync.build import build as build
from .sync.build import save_baseline as save_baseline
from .sync.comparison import compare as compare
from .sync.merge import merge_body as merge_body
from .sync.merge import merge_value as merge_value
from .sync.pull import prepare_pull as prepare_pull
from .sync.semantic import semantic_block


def semantic(step: Mapping[str, object]) -> JsonObject:
    """Retain the original dictionary helper for existing author scripts."""
    return semantic_block(parse_block(step["block"])).to_dict()
