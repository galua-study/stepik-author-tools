"""Parse supported grading layouts and compile their Stepik source settings."""

from ..config.authoring import ExercisePatterns
from ..domain.models import ChoiceOption, MatchingPair, StepSource
from .markup import fragment


def numbered(text: str, rules: ExercisePatterns) -> list[str]:
    """Read consecutive top-level options, preserving continuation/code content."""
    matches = list(rules.numbered_item.finditer(text))
    if not matches:
        matches = list(rules.option_heading.finditer(text))
    indices = [int(match["number"]) for match in matches]
    if indices != list(range(1, len(matches) + 1)) or len(matches) < 2:
        raise ValueError("Expected at least two consecutively numbered options")
    values = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[match.end() : end].strip()
        values.append("\n".join(line.removeprefix("   ") for line in value.split("\n")))
    return values


def correct_indices(answer: str, option_count: int, rules: ExercisePatterns) -> list[int]:
    """Parse numeric/bold/bulleted answer keys and reject out-of-range duplicates."""
    plain = answer.replace("**", "")
    first = plain.partition("\n")[0]
    match = rules.answer_list.match(first)
    bullets = [bullet["number"] for bullet in rules.bullet_answer.finditer(plain)]
    if bullets:
        numbers = bullets
    elif match:
        numbers = rules.answer_separator.split(match["numbers"])
    else:
        raise ValueError("Correct answer must start with option numbers")
    correct = [int(value) for value in numbers]
    if len(set(correct)) != len(correct) or any(n < 1 or n > option_count for n in correct):
        raise ValueError("Invalid correct-answer indices")
    return correct


def choice_source(
    options_text: str, answer: str, metadata: str, rules: ExercisePatterns
) -> StepSource:
    """Compile an ordered choice task without placing keys in student HTML."""
    options = numbered(options_text, rules)
    correct = correct_indices(answer, len(options), rules)
    multiple = bool(rules.multiple_choice.search(metadata))
    return StepSource(
        is_multiple_choice=multiple or len(correct) > 1,
        is_always_correct=False,
        sample_size=len(options),
        preserve_order=True,
        is_html_enabled=True,
        is_options_feedback=False,
        options=[
            ChoiceOption(text=fragment(value), is_correct=index in correct, feedback="")
            for index, value in enumerate(options, 1)
        ],
    )


def _right_column(text: str, rules: ExercisePatterns) -> dict[str, str]:
    matches = list(rules.right_item.finditer(text))
    result = {}
    for index, match in enumerate(matches):
        if match["letter"] in result:
            raise ValueError("Duplicate right-column label")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match["letter"]] = text[match.end() : end].strip()
    return result


def matching_source(
    left_text: str, right_text: str, answer: str, rules: ExercisePatterns
) -> StepSource:
    """Compile a complete one-to-one matching key in the original left order."""
    left = numbered(left_text, rules)
    right = _right_column(right_text, rules)
    keys = list(rules.matching_pair.finditer(answer))
    mapping = {int(match["number"]): match["letter"] for match in keys}
    complete = set(mapping) == set(range(1, len(left) + 1))
    unique = len(mapping) == len(keys) and len(set(mapping.values())) == len(left)
    if not complete or not unique or set(mapping.values()) != set(right):
        raise ValueError("Matching requires a complete one-to-one answer map")
    return StepSource(
        preserve_firsts_order=True,
        is_html_enabled=True,
        pairs=[
            MatchingPair(first=fragment(value), second=fragment(right[mapping[index]]))
            for index, value in enumerate(left, 1)
        ],
    )
