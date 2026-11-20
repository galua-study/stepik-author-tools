"""Shared Pydantic checks for settings, regex groups and Markdown formatting templates."""

import re
from string import Formatter

from pydantic import AfterValidator, BaseModel, ConfigDict


class ConfigModel(BaseModel):
    """Reject unknown settings so a misspelled override cannot silently disappear."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


def captures(*names: str) -> AfterValidator:
    """Check named captures before a pattern sees any course material."""

    def validate(pattern: re.Pattern[str]) -> re.Pattern[str]:
        missing = set(names) - pattern.groupindex.keys()
        if missing:
            raise ValueError(f"Pattern requires named groups: {', '.join(sorted(missing))}")
        return pattern

    return AfterValidator(validate)


def placeholders(*names: str) -> AfterValidator:
    """Require simple named placeholders in a grading output template."""

    def validate(template: str) -> str:
        fields = set()
        for _, name, spec, conversion in Formatter().parse(template):
            if name is not None:
                if spec or conversion:
                    raise ValueError("Grading placeholders accept plain values")
                fields.add(name)
        if fields != set(names):
            raise ValueError(f"Expected placeholders: {', '.join(names)}")
        return template

    return AfterValidator(validate)
