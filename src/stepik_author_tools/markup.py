"""Conservative HTML normalization: literal code and meaningful attributes survive."""

import re
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"html": True}).enable("table")


def render(value: str) -> str:
    return _md.render(value).strip()


def fragment(value: str) -> str:
    html = render(value)
    soup = BeautifulSoup(html, "html.parser")
    if len(soup.contents) == 1 and soup.p:
        return soup.p.decode_contents()
    return html


def canonical(value: str) -> str:
    soup = BeautifulSoup(value.replace("\r\n", "\n"), "html.parser")
    for node in soup.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()
    for tag in soup.find_all(True):
        tag.name = {"b": "strong", "i": "em"}.get(tag.name, tag.name)
        attrs = {}
        for key, val in tag.attrs.items():
            if key == "class":
                if tag.name == "code":
                    lang = [v for v in val if v.startswith("language-")]
                    if lang:
                        attrs[key] = lang
            elif key != "id" and not key.startswith("data-") and key != "contenteditable":
                attrs[key] = val
        tag.attrs = attrs
    for node in list(soup.find_all(string=True)):
        if node.find_parent(["pre", "code", "script", "style"]):
            continue
        normalized = re.sub(r"\s+", " ", str(node).replace("\xa0", " "))
        if not normalized.strip() and (node.parent == soup or node.parent.name in {"div", "ul", "ol", "table", "thead", "tbody", "tr"}):
            node.extract()
        else:
            node.replace_with(normalized)
    for tag in list(soup.find_all(["span", "div"])):
        if not tag.attrs and tag.name == "span":
            tag.unwrap()
        elif not tag.attrs and any(isinstance(n, Tag) and n.name in {"p", "pre", "h2", "h3", "ul", "ol", "table"} for n in tag.children):
            tag.unwrap()
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
        if tag.contents and isinstance(tag.contents[0], NavigableString):
            tag.contents[0].replace_with(str(tag.contents[0]).lstrip())
        if tag.contents and isinstance(tag.contents[-1], NavigableString):
            tag.contents[-1].replace_with(str(tag.contents[-1]).rstrip())
    return str(soup).strip()


def blocks(value: str) -> list[str]:
    return [str(n) for n in BeautifulSoup(canonical(value), "html.parser").contents]


def code_blocks(value: str) -> list[str]:
    return [n.get_text() for n in BeautifulSoup(value, "html.parser").find_all("pre")]
