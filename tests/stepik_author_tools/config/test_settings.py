"""Default isolation and validation of TOML project profiles."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from stepik_author_tools import load_settings
from stepik_author_tools.domain.enums import SemanticField


def test_partial_profiles_preserve_other_defaults_and_are_isolated(tmp_path: Path) -> None:
    config = tmp_path / "author.toml"
    config.write_text(
        '[api]\nmax_pages = 2\n[diff.fields]\nanswers = "Новый ключ"\n', encoding="utf-8-sig"
    )
    settings = load_settings(config)
    assert settings.api.max_pages == 2
    assert settings.diff.fields[SemanticField.ANSWERS] == "Новый ключ"
    assert settings.diff.code == load_settings().diff.code
    assert load_settings().api.max_pages == 10_000
    assert load_settings().diff.fields[SemanticField.ANSWERS] == "correct answer changed"


def test_new_alias_preserves_existing_author_boundaries(tmp_path: Path) -> None:
    config = tmp_path / "course.toml"
    config.write_text('[markdown.author_sections]\nanswer = ["Key"]', encoding="utf-8")
    aliases = load_settings(config).markdown.author_sections["answer"]
    assert {"Key", "Correct answer", "Правильный ответ"} <= set(aliases)


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ("[api]\nmax_pages = 0", "max_pages"),
        ('[api]\nresources = ["../steps"]', "resources"),
        ('[api]\nbase_url = "http://example.test/"', "base_url"),
        ('[api]\nbase_url = "https://name@example.test/"', "base_url"),
        ('[project]\nmanifest_name = "../outside.json"', "manifest_name"),
        ('[markdown.patterns]\nnumbered_item = "("', "numbered_item"),
        ('[markdown.patterns]\nnumbered_item = "(missing_named_capture)"', "number"),
        ('[markdown.format]\nnumbered_item = "{indx}. {text}"', "placeholders"),
        ('[markdown.author_sections]\nreview = ["Condition"]', "one role"),
        ('[diff.fields]\nunknown_field = "Changed"', "unknown_field"),
        ("[api]\nmax_page = 1", "max_page"),
    ],
)
def test_invalid_profile_identifies_the_setting(tmp_path: Path, override: str, field: str) -> None:
    config = tmp_path / "invalid.toml"
    config.write_text(override, encoding="utf-8")
    with pytest.raises(ValidationError, match=field):
        load_settings(config)
