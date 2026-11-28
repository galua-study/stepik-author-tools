"""Project merged semantic values back into an existing author document."""

from collections.abc import Iterable
from string import ascii_uppercase

from ..config.authoring import GradingFormat, MarkdownSettings
from ..domain.models import SemanticStep
from ..markdown.markup import blocks
from ..markdown.material import Material
from .semantic import semantic_block


def _student_body(material: Material, local: str, merged: str) -> str:
    merged_blocks = blocks(merged)
    if material.task:
        local_blocks = blocks(local)
        if not merged_blocks or not local_blocks or merged_blocks[0] != local_blocks[0]:
            raise ValueError("Exercise title change requires manual review")
        # The task heading comes from its own Markdown line, outside the condition
        merged_blocks = merged_blocks[1:]
    # A blank line separates CommonMark HTML blocks, including multiline code
    return "\n\n".join(merged_blocks)


def _numbered(values: Iterable[str], style: GradingFormat) -> str:
    return "\n".join(
        style.numbered_item.format(number=i, text=text) for i, text in enumerate(values, 1)
    )


def _replace_pairs(material: Material, pairs: tuple[tuple[str, str], ...]) -> None:
    if len(pairs) > len(ascii_uppercase):
        raise ValueError("More than 26 matching pairs require manual review")
    style = material.dialect.format
    letters = ascii_uppercase[: len(pairs)]
    material.replace("left", _numbered((first for first, _ in pairs), style))
    right = (
        style.right_item.format(letter=letter, text=pair[1])
        for letter, pair in zip(letters, pairs, strict=True)
    )
    material.replace("right", "\n".join(right))
    answer = (
        style.matching_pair.format(number=i, letter=letter) for i, letter in enumerate(letters, 1)
    )
    material.replace("answer", style.answer_separator.join(answer))


def project_material(
    original: str, local: SemanticStep, merged: SemanticStep, dialect: MarkdownSettings
) -> str:
    """Edit only changed source sections and verify their exact semantic round trip.

    Raw HTML intentionally avoids a lossy HTML-to-Markdown conversion. A failed
    rebuild is a review conflict rather than a partially trustworthy source patch.
    """
    material = Material(original, dialect)
    if merged.body != local.body:
        material.replace_body(_student_body(material, local.body, merged.body))
    if merged.options != local.options:
        material.replace("options", _numbered(merged.options, dialect.format))
    if merged.answers != local.answers:
        material.replace("answer", dialect.format.answer_separator.join(map(str, merged.answers)))
    if merged.pairs != local.pairs:
        _replace_pairs(material, merged.pairs)
    if semantic_block(material.compile()) != merged:
        raise ValueError("Round-trip check failed; source needs manual review")
    return material.text
