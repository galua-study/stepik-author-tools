"""Project merged semantic values back into an existing author document."""

from bs4 import BeautifulSoup

from ..domain.models import SemanticStep
from ..markdown.markup import blocks, canonical
from ..markdown.material import Material
from .semantic import semantic_block


def _student_body(material: Material, local: str, merged: str) -> str:
    if not material.task:
        return merged
    soup = BeautifulSoup(merged, "html.parser")
    old = BeautifulSoup(local, "html.parser")
    if not soup.contents or not old.contents:
        raise ValueError("Exercise title change requires manual review")
    if canonical(str(soup.contents[0])) != canonical(str(old.contents[0])):
        raise ValueError("Exercise title change requires manual review")
    soup.contents[0].extract()
    return str(soup)


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
        body = _student_body(material, local.body, merged.body)
        # Each pre must start on a new block; otherwise CommonMark ends an ordinary
        # HTML block on an internal blank line and parses the remaining code as prose.
        material.replace_body("\n\n".join(blocks(body)))
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
