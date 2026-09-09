"""Offline JSON Schema validation with safe diagnostics."""

import json
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]


class ToolSchemaError(ValueError):
    pass


class ToolArgumentsError(ValueError):
    pass


def validate_schema(schema: dict[str, Any]) -> None:
    try:
        json.dumps(schema, allow_nan=False)
        if schema.get("$schema", "https://json-schema.org/draft/2020-12/schema") not in {
            "https://json-schema.org/draft/2020-12/schema",
            "https://json-schema.org/draft/2020-12/schema#",
        }:
            raise ValueError("unsupported dialect")

        def check_refs(value: object) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {"$ref", "$dynamicRef"} and (
                        not isinstance(child, str) or not child.startswith("#")
                    ):
                        raise ValueError("external reference")
                    if key == "$id":
                        raise ValueError("resource identifiers unsupported")
                    check_refs(child)
            elif isinstance(value, list):
                for child in value:
                    check_refs(child)

        check_refs(schema)
        Draft202012Validator.check_schema(schema)
    except Exception:
        raise ToolSchemaError("invalid_tool_schema") from None


def validate_arguments(schema: dict[str, Any], arguments: object) -> None:
    try:
        # Reject non-JSON values, NaN and infinity before transport serialization.
        json.dumps(arguments, allow_nan=False)
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be an object")
        validate_schema(schema)
        Draft202012Validator(schema).validate(arguments)
    except Exception:
        raise ToolArgumentsError("invalid_tool_arguments") from None
