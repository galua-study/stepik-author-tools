"""Parse supported grading layouts and compile their Stepik source settings."""

import re

from ..domain.models import StepSource
from .markup import fragment


def numbered(text: str) -> list[str]:
    """Read consecutive top-level options, preserving continuation/code content."""
    matches = list(re.finditer(r"(?m)^(\d+)\.\s+", text))
    if not matches:
        matches = list(re.finditer(r"(?m)^(?:Вариант|Option) (\d+):\s*\n", text))
    indices = [int(match[1]) for match in matches]
    if indices != list(range(1, len(matches) + 1)) or len(matches) < 2:
        raise ValueError("Expected at least two consecutively numbered options")
    values = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[match.end() : end].strip()
        values.append(re.sub(r"(?m)^ {3}", "", value))
    return values


def correct_indices(answer: str, option_count: int) -> list[int]:
    """Parse numeric/bold/bulleted answer keys and reject out-of-range duplicates."""
    first = answer.splitlines()[0].replace("**", "") if answer else ""
    match = re.match(r"^\s*(\d+(?:\s*[,;иand ]\s*\d+)*)[.)]?(?:\s|$)", first)
    bullets = re.findall(r"(?m)^-\s+(\d+)\.", answer.replace("**", ""))
    if bullets:
        numbers = bullets
    elif match:
        numbers = re.findall(r"\d+", match[1])
    else:
        raise ValueError("Correct answer must start with option numbers")
    correct = [int(value) for value in numbers]
    if len(set(correct)) != len(correct) or any(n < 1 or n > option_count for n in correct):
        raise ValueError("Invalid correct-answer indices")
    return correct


def choice_source(options_text: str, answer: str, metadata: str) -> StepSource:
    """Compile an ordered choice task without placing keys in student HTML."""
    options = numbered(options_text)
    correct = correct_indices(answer, len(options))
    multiple = bool(re.search(r"несколько|несколькими|multiple", metadata, re.I))
    return {
        "is_multiple_choice": multiple or len(correct) > 1,
        "is_always_correct": False,
        "sample_size": len(options),
        "preserve_order": True,
        "is_html_enabled": True,
        "is_options_feedback": False,
        "options": [
            {"text": fragment(value), "is_correct": index in correct, "feedback": ""}
            for index, value in enumerate(options, 1)
        ],
    }


def _right_column(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^- \*\*([A-ZА-Я]+)\*\*\s*[—–-]\s*", text))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match[1]] = text[match.end() : end].strip()
    return result


def matching_source(left_text: str, right_text: str, answer: str) -> StepSource:
    """Compile a complete one-to-one matching key in the original left order."""
    left = numbered(left_text)
    right = _right_column(right_text)
    keys = re.findall(r"(\d+)\s*[—–-]\s*([A-ZА-Я]+)", answer)
    mapping = {int(number): letter for number, letter in keys}
    complete = set(mapping) == set(range(1, len(left) + 1))
    unique = len(mapping) == len(keys) and len(set(mapping.values())) == len(left)
    if not complete or not unique or set(mapping.values()) != set(right):
        raise ValueError("Matching requires a complete one-to-one answer map")
    return {
        "preserve_firsts_order": True,
        "is_html_enabled": True,
        "pairs": [
            {"first": fragment(value), "second": fragment(right[mapping[index]])}
            for index, value in enumerate(left, 1)
        ],
    }
