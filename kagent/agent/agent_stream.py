from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

TextDeltaFn = Callable[[str], None]


@dataclass
class AggregatedFunction:
    name: str
    arguments: str


@dataclass
class AggregatedToolCall:
    id: str
    type: str
    function: AggregatedFunction


@dataclass
class AggregatedAssistantMessage:
    content: str
    tool_calls: list[AggregatedToolCall]

    def model_dump(self, exclude_none: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {"role": "assistant"}
        if self.content or not exclude_none:
            data["content"] = self.content
        if self.tool_calls:
            data["tool_calls"] = [
                {
                    "id": call.id,
                    "type": call.type,
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in self.tool_calls
            ]
        return data


def aggregate_chat_completion_stream(
    stream: Iterable[Any],
    *,
    on_text_delta: TextDeltaFn | None = None,
) -> AggregatedAssistantMessage:
    content_parts: list[str] = []
    tool_parts: dict[int, dict[str, Any]] = {}

    for chunk in stream:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        delta = getattr(choices[0], "delta", None)
        if delta is None:
            continue

        content = getattr(delta, "content", None)
        if content:
            content_parts.append(str(content))
            if on_text_delta:
                on_text_delta(str(content))

        for tool_delta in getattr(delta, "tool_calls", None) or []:
            index = int(getattr(tool_delta, "index", 0) or 0)
            target = tool_parts.setdefault(
                index,
                {
                    "id": "",
                    "type": "function",
                    "name": "",
                    "arguments": [],
                },
            )
            call_id = getattr(tool_delta, "id", None)
            if call_id:
                target["id"] = str(call_id)
            call_type = getattr(tool_delta, "type", None)
            if call_type:
                target["type"] = str(call_type)

            function = getattr(tool_delta, "function", None)
            if function is None:
                continue
            name = getattr(function, "name", None)
            if name:
                target["name"] = str(target.get("name") or "") + str(name)
            arguments = getattr(function, "arguments", None)
            if arguments:
                target["arguments"].append(str(arguments))

    tool_calls = [
        AggregatedToolCall(
            id=str(parts.get("id") or f"tool-call-{index}"),
            type=str(parts.get("type") or "function"),
            function=AggregatedFunction(
                name=str(parts.get("name") or ""),
                arguments="".join(parts.get("arguments") or []),
            ),
        )
        for index, parts in sorted(tool_parts.items())
    ]
    return AggregatedAssistantMessage(
        content="".join(content_parts),
        tool_calls=tool_calls,
    )
