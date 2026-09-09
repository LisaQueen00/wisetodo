"""Deterministic candidate filtering, independent of models and input parsers."""

import re
from collections.abc import Iterable

from wisetodo.skills.metadata import ValidatedSkill


def select_skills(
    skills: Iterable[ValidatedSkill], input_types: Iterable[str]
) -> tuple[ValidatedSkill, ...]:
    """Match any declared type exactly and preserve the supplied snapshot order.

    Types describe already identified input objects, not user intent. Unknown but
    well-formed types are supported for future parsers. No filesystem or network
    access, tool availability checks, ranking, or instruction injection occurs here.
    """
    if isinstance(input_types, str):
        raise ValueError("Expected a collection of input types")
    types: set[str] = set()
    for kind in input_types:
        if not isinstance(kind, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", kind):
            raise ValueError("Invalid input type")
        types.add(kind)
    if not types:
        return ()
    return tuple(skill for skill in skills if types.intersection(skill.metadata.accepts))


def filter_available_skills(
    skills: Iterable[ValidatedSkill], tool_names: Iterable[str]
) -> tuple[ValidatedSkill, ...]:
    """Keep candidates whose required tools are all in the caller's Run snapshot.

    Optional dependencies never disable a Skill. This checks names only, not tool
    health or execution permissions; the caller supplies vetted available tools.
    """
    if isinstance(tool_names, str):
        raise ValueError("Expected a collection of tool names")
    available = set(tool_names)
    return tuple(skill for skill in skills if available.issuperset(skill.metadata.required_tools))
