"""Final model-facing tool-result budgets, independent of transport byte limits."""

import copy
import json

from pydantic import JsonValue

PER_RESULT_CHARS = 16_000
BATCH_RESULT_CHARS = 32_000


class ToolResultBudgetError(ValueError):
    pass


def model_tool_results(results: dict[str, JsonValue]) -> dict[str, JsonValue]:
    omitted: JsonValue = {
        "omitted": True,
        "reason": "content_budget",
        "notice": "工具结果过大，未提供内容；不可视为已读取，请请求更小范围资料或澄清。",
    }
    bounded = {key: copy.deepcopy(omitted) for key in results}
    if len(json.dumps(bounded, ensure_ascii=False)) > BATCH_RESULT_CHARS:
        raise ToolResultBudgetError("tool_result_budget_exceeded")
    for key, value in results.items():
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(encoded) > PER_RESULT_CHARS:
            continue
        bounded[key] = copy.deepcopy(value)
        if len(json.dumps(bounded, ensure_ascii=False)) > BATCH_RESULT_CHARS:
            bounded[key] = copy.deepcopy(omitted)
    return bounded
