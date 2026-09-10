"""Lossy, deterministic model-facing history limits; storage is never modified."""

from collections.abc import Sequence

from wisetodo.model.contracts import ModelMessage

HISTORY_MAX_CHARS = 32_000
HISTORY_MAX_MESSAGES = 64
MESSAGE_MAX_CHARS = 8_000
OMITTED = "\n[历史已裁剪，部分内容省略；缺少必要事实时请澄清。]\n"
CLIPPED = "\n[此消息中间内容已省略]\n"


def bounded_history(messages: Sequence[ModelMessage]) -> list[ModelMessage]:
    """Keep first goal and a recent suffix, in order, with explicit loss markers.

    Only user/assistant chat belongs here, before application context is appended.
    Limits count Python characters, not tokens or the entire provider request.
    """
    if any(message.role not in {"user", "assistant"} for message in messages):
        raise ValueError("Only chat messages may be trimmed")
    if not messages:
        return []
    clipped = []
    changed = False
    for message in messages:
        content = message.content
        if len(content) > MESSAGE_MAX_CHARS:
            head = (MESSAGE_MAX_CHARS - len(CLIPPED)) // 2
            tail = MESSAGE_MAX_CHARS - len(CLIPPED) - head
            content = content[:head] + CLIPPED + content[-tail:]
            changed = True
        clipped.append(message.model_copy(update={"content": content}, deep=True))
    first = clipped[0]
    remaining = HISTORY_MAX_CHARS - len(OMITTED) - len(first.content)
    recent: list[ModelMessage] = []
    for message in reversed(clipped[1:]):
        if len(recent) == HISTORY_MAX_MESSAGES - 1 or len(message.content) > remaining:
            break
        recent.append(message)
        remaining -= len(message.content)
    selected = [first, *reversed(recent)]
    if changed or len(selected) != len(messages):
        selected[0] = first.model_copy(update={"content": OMITTED + first.content})
    return selected
