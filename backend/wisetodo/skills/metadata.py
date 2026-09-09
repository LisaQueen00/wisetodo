"""Validate the small, declarative WiseTodo Skill header format."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from wisetodo.skills.loader import (
    MAX_SKILL_BYTES,
    SkillDocument,
    SkillDocumentError,
    SkillLoadIssue,
    scan_skills,
)


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    accepts: tuple[str, ...]
    required_tools: tuple[str, ...] = ()
    optional_tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidatedSkill:
    document: SkillDocument
    metadata: SkillMetadata


@dataclass(frozen=True)
class SkillLoad:
    skills: tuple[ValidatedSkill, ...]
    issues: tuple[SkillLoadIssue, ...]


def _mapping(value: object, allowed: set[str], required: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise SkillDocumentError("invalid_metadata")
    if not required <= value.keys() or value.keys() - allowed:
        raise SkillDocumentError("invalid_metadata")
    return dict(value)


def _names(value: object, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (nonempty and not value):
        raise SkillDocumentError("invalid_metadata")
    names: list[str] = []
    for item in value:
        if not isinstance(item, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", item):
            raise SkillDocumentError("invalid_metadata")
        if item in names:
            raise SkillDocumentError("duplicate_metadata_value")
        names.append(item)
    return tuple(names)


def _read_yaml(text: str) -> object:
    # Inspect events before construction: bound nesting and reject aliases/anchors.
    # SafeLoader constructors are never extended with executable application objects.
    if len(text.encode("utf-8")) > MAX_SKILL_BYTES:
        raise SkillDocumentError("document_too_large")
    try:
        depth = 0
        for event in yaml.parse(text, Loader=yaml.SafeLoader):
            if isinstance(event, yaml.events.AliasEvent) or getattr(event, "anchor", None):
                raise SkillDocumentError("yaml_alias_not_allowed")
            if isinstance(event, (yaml.events.MappingStartEvent, yaml.events.SequenceStartEvent)):
                depth += 1
                if depth > 8:
                    raise SkillDocumentError("yaml_too_deep")
            elif isinstance(event, (yaml.events.MappingEndEvent, yaml.events.SequenceEndEvent)):
                depth -= 1
        node = yaml.compose(text, Loader=yaml.SafeLoader)

        def convert(current: object) -> object:
            if isinstance(current, yaml.nodes.ScalarNode):
                if current.tag != "tag:yaml.org,2002:str":
                    raise SkillDocumentError("invalid_yaml_type")
                return str(current.value)
            if isinstance(current, yaml.nodes.SequenceNode):
                if current.tag != "tag:yaml.org,2002:seq":
                    raise SkillDocumentError("invalid_yaml_type")
                return [convert(child) for child in current.value]
            if isinstance(current, yaml.nodes.MappingNode):
                if current.tag != "tag:yaml.org,2002:map":
                    raise SkillDocumentError("invalid_yaml_type")
                result: dict[str, object] = {}
                for key_node, value_node in current.value:
                    key = convert(key_node)
                    if not isinstance(key, str):
                        raise SkillDocumentError("invalid_metadata")
                    if key in result:
                        raise SkillDocumentError("duplicate_yaml_key")
                    result[key] = convert(value_node)
                return result
            raise SkillDocumentError("invalid_metadata")

        return convert(node)
    except yaml.YAMLError:
        raise SkillDocumentError("invalid_yaml") from None


def validate_skill_document(document: SkillDocument) -> ValidatedSkill:
    """Return immutable metadata; errors contain codes, never YAML contents."""
    header = _mapping(
        _read_yaml(document.frontmatter),
        {"name", "description", "accepts", "tools"},
        {"name", "description", "accepts"},
    )
    name = header["name"]
    description = header["description"]
    if (
        not isinstance(name, str)
        or len(name) > 64
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
        or not isinstance(description, str)
        or not description.strip()
    ):
        raise SkillDocumentError("invalid_metadata")
    tools = _mapping(header.get("tools", {}), {"required", "optional"}, set())
    required = _names(tools.get("required", []))
    optional = _names(tools.get("optional", []))
    if set(required) & set(optional):
        raise SkillDocumentError("conflicting_tool_dependencies")
    return ValidatedSkill(
        document,
        SkillMetadata(
            name, description.strip(), _names(header["accepts"], nonempty=True), required, optional
        ),
    )


def load_skills(root: Path) -> SkillLoad:
    """Scan and validate independently, retaining diagnostics for rejected files."""
    scan = scan_skills(root)
    skills: list[ValidatedSkill] = []
    issues = list(scan.issues)
    for document in scan.documents:
        try:
            skills.append(validate_skill_document(document))
        except SkillDocumentError as error:
            issues.append(SkillLoadIssue(document.path, str(error)))
    return SkillLoad(tuple(skills), tuple(issues))
