"""Parse course Markdown without publishing author-only sections."""

from dataclasses import dataclass
import re

from .markup import render, fragment

ALIASES = {
    "condition": ("Condition", "Условие"),
    "options": ("Options", "Варианты ответа"),
    "answer": ("Correct answer", "Correct answers", "Правильный ответ", "Правильные ответы", "Правильное решение", "Reference solution"),
    "explanation": ("Explanation", "Объяснение"),
    "left": ("Left column", "Левая колонка"),
    "right": ("Right column", "Правая колонка"),
    "transfer": ("Transfer notes", "Для переноса в Stepik"),
}


def headings(text: str) -> list[tuple[str, int, int]]:
    result = []
    offset = 0
    fence = None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None:
            match = re.match(r"^### (.+?)\s*$", line)
            if match:
                result.append((match[1], offset, offset + len(line)))
        offset += len(line)
    return result


@dataclass
class Material:
    text: str

    def section(self, key: str) -> tuple[int, int] | None:
        items = headings(self.text)
        for i, (title, _, start) in enumerate(items):
            if title in ALIASES[key]:
                return start, items[i + 1][1] if i + 1 < len(items) else len(self.text)
        return None

    def get(self, key: str) -> str:
        span = self.section(key)
        return self.text[slice(*span)].strip() if span else ""

    def replace(self, key: str, value: str) -> None:
        span = self.section(key)
        if span is None:
            raise ValueError(f"Missing section: {key}")
        a, b = span
        self.text = self.text[:a] + "\n" + value.strip() + "\n\n" + self.text[b:]

    @property
    def task(self) -> bool:
        return self.section("condition") is not None

    @property
    def title(self) -> str:
        title = re.sub(r"^#+\s*", "", self.text.splitlines()[0])
        return re.sub(r"^(?:Задание|Task)\s+[\d.]+\s*", "", title)

    def body_span(self) -> tuple[int, int]:
        start = self.section("condition")[0]
        boundaries = [self.section(k)[0] for k in ("options", "left", "right", "answer", "explanation", "transfer") if self.section(k)]
        # Stop at the heading, not the content of the next author section.
        end = min(boundaries, default=len(self.text))
        for _, heading_start, content_start in headings(self.text):
            if content_start == end:
                end = heading_start
        return start, end

    def body(self) -> str:
        return self.text[slice(*self.body_span())].strip() if self.task else self.text.strip()

    def replace_body(self, html: str) -> None:
        if self.task:
            a, b = self.body_span()
            self.text = self.text[:a] + "\n" + html.strip() + "\n\n" + self.text[b:]
        else:
            self.text = html.strip() + "\n"

    def compile(self) -> dict:
        kind, source = "text", {}
        metadata = re.search(r"(?m)^\*\*(?:Тип|Type):\*\*\s*([^\n]+)", self.text)
        if not self.task and (metadata or self.section("answer") or self.section("explanation")):
            raise ValueError("Exercise/author sections require an explicit Condition heading")
        if self.task:
            if self.get("options"):
                options = numbered(self.get("options"))
                answer = self.get("answer")
                first = answer.splitlines()[0].replace("**", "") if answer else ""
                match = re.match(r"^\s*(\d+(?:\s*[,;иand ]\s*\d+)*)[.)]?(?:\s|$)", first)
                bullets = re.findall(r"(?m)^-\s+(\d+)\.", answer.replace("**", ""))
                if not match and not bullets:
                    raise ValueError("Correct answer must start with option numbers")
                correct = [int(v) for v in (bullets or re.findall(r"\d+", match[1]))]
                if not correct or len(set(correct)) != len(correct) or any(n < 1 or n > len(options) for n in correct):
                    raise ValueError("Invalid correct-answer indices")
                multiple = bool(re.search(r"несколько|несколькими|multiple", self.text[:self.body_span()[0]], re.I))
                if len(correct) > 1:
                    multiple = True
                kind = "choice"
                source = dict(is_multiple_choice=multiple, is_always_correct=False,
                              sample_size=len(options), preserve_order=True, is_html_enabled=True,
                              is_options_feedback=False,
                              options=[dict(text=fragment(v), is_correct=i in correct, feedback="") for i, v in enumerate(options, 1)])
            elif self.get("left"):
                left = numbered(self.get("left"))
                matches = list(re.finditer(r"(?m)^- \*\*([A-ZА-Я]+)\*\*\s*[—–-]\s*", self.get("right")))
                right = {m[1]: self.get("right")[m.end():matches[i+1].start() if i+1 < len(matches) else None].strip() for i, m in enumerate(matches)}
                keys = re.findall(r"(\d+)\s*[—–-]\s*([A-ZА-Я]+)", self.get("answer"))
                mapping = {int(n): letter for n, letter in keys}
                if set(mapping) != set(range(1, len(left)+1)) or len(mapping) != len(keys) or set(mapping.values()) != set(right) or len(set(mapping.values())) != len(left):
                    raise ValueError("Matching requires a complete one-to-one answer map")
                kind = "matching"
                source = dict(preserve_firsts_order=True, is_html_enabled=True,
                              pairs=[dict(first=fragment(v), second=fragment(right[mapping[i]])) for i, v in enumerate(left, 1)])
            elif re.search(r"сортиров|сопоставлен|упорядочив|sorting|matching", self.text[:self.body_span()[0]], re.I):
                raise ValueError("Unsupported exercise layout; use Left column / Right column for matching")
            elif metadata and not re.search(r"самопровер|self.check", metadata[1], re.I):
                raise ValueError("Unsupported exercise type; only explicit local self-check tasks become text")
        text = render("## " + self.title + "\n\n" + self.body()) if self.task else render(self.body())
        return dict(name=kind, text=text, source=source, options={}, is_deprecated=False,
                    video=None, subtitles={}, subtitle_files=[], tests_archive=None,
                    feedback_correct="", feedback_wrong="")


def numbered(text: str) -> list[str]:
    # Top-level markers only; indented continuation paragraphs/code stay in the item.
    matches = list(re.finditer(r"(?m)^(\d+)\.\s+", text))
    if not matches:
        matches = list(re.finditer(r"(?m)^(?:Вариант|Option) (\d+):\s*\n", text))
    if [int(m[1]) for m in matches] != list(range(1, len(matches)+1)) or len(matches) < 2:
        raise ValueError("Expected at least two consecutively numbered options")
    values = []
    for i, m in enumerate(matches):
        value = text[m.end():matches[i+1].start() if i+1 < len(matches) else None].strip()
        values.append(re.sub(r"(?m)^ {3}", "", value))
    return values
