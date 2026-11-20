"""Project merged semantic values back into an existing author document."""

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
        # The task heading comes from its own Markdown line, outside the condition.
        merged_blocks = merged_blocks[1:]
    # A blank line separates CommonMark HTML blocks, including multiline code.
    return "\n\n".join(merged_blocks)


def _replace_pairs(material: Material, pairs: tuple[tuple[str, str], ...]) -> None:
    if len(pairs) > 26:
        raise ValueError("More than 26 matching pairs require manual review")
    material.replace("left", "\n".join(f"{i}. {pair[0]}" for i, pair in enumerate(pairs, 1)))
    material.replace(
        "right", "\n".join(f"- **{chr(65 + i)}** — {pair[1]}" for i, pair in enumerate(pairs))
    )
    material.replace("answer", ", ".join(f"{i + 1} — {chr(65 + i)}" for i in range(len(pairs))))


def project_material(original: str, local: SemanticStep, merged: SemanticStep) -> str:
    """Edit only changed source sections and verify their exact semantic round trip.

    Raw HTML intentionally avoids a lossy HTML-to-Markdown conversion. A failed
    rebuild is a review conflict rather than a partially trustworthy source patch.
    """
    material = Material(original)
    if merged.body != local.body:
        material.replace_body(_student_body(material, local.body, merged.body))
    if merged.options != local.options:
        material.replace(
            "options", "\n".join(f"{i}. {value}" for i, value in enumerate(merged.options, 1))
        )
    if merged.answers != local.answers:
        material.replace("answer", ", ".join(map(str, merged.answers)))
    if merged.pairs != local.pairs:
        _replace_pairs(material, merged.pairs)
    if semantic_block(material.compile()) != merged:
        raise ValueError("Round-trip check failed; source needs manual review")
    return material.text
