"""Conservative HTML normalization that preserves literal code and meaningful attributes."""

import re

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag
from markdown_it import MarkdownIt

MARKDOWN = MarkdownIt("commonmark", {"html": True}).enable("table")
_HTML_WHITESPACE = re.compile(r"\s+")
_BLOCK_CONTAINERS = {"div", "ul", "ol", "table", "thead", "tbody", "tr"}
_WRAPPED_BLOCKS = {"p", "pre", "h2", "h3", "ul", "ol", "table"}


def render(value: str) -> str:
    """Render CommonMark with tables and source-provided HTML enabled."""
    html = MARKDOWN.render(value)
    # MarkdownIt supports custom non-HTML renderers; this instance must return HTML.
    if not isinstance(html, str):
        raise ValueError("Markdown renderer did not return HTML text")
    return html.strip()


def fragment(value: str) -> str:
    """Render an option without a redundant single-paragraph wrapper."""
    html = render(value)
    soup = BeautifulSoup(html, "html.parser")
    if len(soup.contents) == 1:
        only = soup.contents[0]
        if isinstance(only, Tag) and only.name == "p" and not only.attrs:
            return only.decode_contents()
    return html


def _clean_attributes(tag: Tag) -> None:
    tag.name = {"b": "strong", "i": "em"}.get(tag.name, tag.name)
    for key in list(tag.attrs):
        if key == "class":
            languages = [
                value
                for value in tag.get_attribute_list("class")
                if value and value.startswith("language-")
            ]
            if tag.name == "code" and languages:
                tag[key] = " ".join(languages)
            else:
                del tag[key]
        elif key in {"id", "contenteditable"} or key.startswith("data-"):
            del tag[key]


def _normalize_text(soup: BeautifulSoup) -> None:
    for node in list(soup.find_all(string=True)):
        if isinstance(node, Comment):
            node.extract()
            continue
        # Code indentation and spaces inside literals are observable course content.
        if node.find_parent(["pre", "code", "script", "style"]):
            continue
        normalized = _HTML_WHITESPACE.sub(" ", str(node))
        parent = node.parent
        between_blocks = parent is soup or (parent is not None and parent.name in _BLOCK_CONTAINERS)
        if not normalized.strip() and between_blocks:
            node.extract()
        else:
            node.replace_with(normalized)


def _unwrap_editor_containers(soup: BeautifulSoup) -> None:
    for tag in list(soup.find_all(["span", "div"])):
        if not isinstance(tag, Tag) or tag.attrs:
            continue
        contains_block = any(
            isinstance(node, Tag) and node.name in _WRAPPED_BLOCKS for node in tag.children
        )
        if tag.name == "span" or contains_block:
            tag.unwrap()


def _trim_block_edges(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
        if not isinstance(tag, Tag) or not tag.contents:
            continue
        first, last = tag.contents[0], tag.contents[-1]
        if first is last and isinstance(first, NavigableString):
            first.replace_with(str(first).strip())
            continue
        if isinstance(first, NavigableString):
            first.replace_with(str(first).lstrip())
        if isinstance(last, NavigableString):
            last.replace_with(str(last).rstrip())


def canonical(value: str) -> str:
    """Remove editor noise while retaining structure, links, styles and literal code."""
    soup = BeautifulSoup(value.replace("\r\n", "\n"), "html.parser")
    for tag in soup.find_all(True):
        if isinstance(tag, Tag):
            _clean_attributes(tag)
    _normalize_text(soup)
    _unwrap_editor_containers(soup)
    _trim_block_edges(soup)
    return str(soup).strip()


def blocks(value: str) -> list[str]:
    """Split normalized HTML into atomic merge units (paragraphs, code blocks, etc.)."""
    parts: list[str] = []
    for node in BeautifulSoup(canonical(value), "html.parser").contents:
        if isinstance(node, Tag):
            parts.append(node.decode())
        elif isinstance(node, NavigableString):
            # Escape literal angle brackets and ampersands before reassembling the HTML.
            parts.append(node.output_ready())
        else:
            raise ValueError(f"Unsupported HTML node: {type(node).__name__}")
    return parts


def code_blocks(value: str) -> list[str]:
    """Extract literal code for a line-oriented explanation of a semantic change."""
    return [node.get_text() for node in BeautifulSoup(value, "html.parser").find_all("pre")]
