import os
import time
from typing import Any, Callable, Iterator

from openai import OpenAI, Stream

from .config import (
    CONTEXT_KEEP_RECENT_MESSAGES,
    CONTEXT_MAX_TOKENS,
    CONTEXT_PER_MESSAGE_MAX_CHARS,
    CONTEXT_SUMMARY_MAX_CHARS,
    MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    REASONING_EFFORT,
    SYSTEM_PROMPT,
    normalize_reasoning_effort,
)
from .context import manage_context

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
CHAT_REQUEST_TIMEOUT_SECONDS = float(os.getenv("KAGENT_CHAT_TIMEOUT_SECONDS", "45"))
STREAM_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("KAGENT_STREAM_TIMEOUT_SECONDS", str(CHAT_REQUEST_TIMEOUT_SECONDS))
)
TITLE_REQUEST_TIMEOUT_SECONDS = float(os.getenv("KAGENT_TITLE_TIMEOUT_SECONDS", "10"))
AGENT_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("KAGENT_AGENT_TIMEOUT_SECONDS", str(CHAT_REQUEST_TIMEOUT_SECONDS))
)


def _reasoning_param(reasoning_effort: str | None) -> dict[str, str]:
    return {"reasoning_effort": normalize_reasoning_effort(reasoning_effort or REASONING_EFFORT)}


def runtime_metadata_prompt(model: str | None, reasoning_effort: str | None) -> str:
    active_model = str(model or MODEL).strip() or MODEL
    active_reasoning = normalize_reasoning_effort(reasoning_effort or REASONING_EFFORT)
    return (
        "Runtime request metadata.\n"
        f"- Current runtime model: {active_model}\n"
        f"- Current reasoning effort: {active_reasoning}\n"
        "If the user asks what model or reasoning effort is currently being used, "
        "answer from this metadata instead of guessing from training data or defaults."
    )


def _is_unsupported_reasoning_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "reasoning_effort" in text and (
        "unsupported" in text
        or "unknown" in text
        or "invalid" in text
        or "unrecognized" in text
        or "extra inputs" in text
        or "not permitted" in text
    )


def create_chat_completion_with_reasoning(
    *,
    reasoning_effort: str | None = None,
    retry_without_reasoning: bool = True,
    on_request_event: Callable[[dict[str, Any]], None] | None = None,
    **kwargs,
):
    started = time.perf_counter()
    model = str(kwargs.get("model") or MODEL)
    normalized_reasoning = normalize_reasoning_effort(reasoning_effort or REASONING_EFFORT)
    metadata = {
        "model": model,
        "reasoning_effort": normalized_reasoning,
        "stream": bool(kwargs.get("stream")),
        "has_tools": bool(kwargs.get("tools")),
        "retry_without_reasoning": bool(retry_without_reasoning),
    }
    _emit_request_event(on_request_event, "model_request", metadata)
    try:
        response = client.chat.completions.create(
            **kwargs,
            **_reasoning_param(normalized_reasoning),
        )
        _emit_request_event(
            on_request_event,
            "model_response",
            {
                **metadata,
                "fallback_without_reasoning": False,
                "duration_ms": _duration_ms(started),
            },
        )
        return response
    except Exception as exc:
        if not retry_without_reasoning or not _is_unsupported_reasoning_error(exc):
            _emit_request_event(
                on_request_event,
                "model_error",
                {
                    **metadata,
                    "fallback_without_reasoning": False,
                    "duration_ms": _duration_ms(started),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            raise
        _emit_request_event(
            on_request_event,
            "model_error",
            {
                **metadata,
                "fallback_without_reasoning": False,
                "will_retry_without_reasoning": True,
                "duration_ms": _duration_ms(started),
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )

    retry_started = time.perf_counter()
    retry_metadata = {
        **metadata,
        "reasoning_effort": None,
        "fallback_without_reasoning": True,
    }
    _emit_request_event(on_request_event, "model_request", retry_metadata)
    try:
        response = client.chat.completions.create(**kwargs)
        _emit_request_event(
            on_request_event,
            "model_response",
            {
                **retry_metadata,
                "duration_ms": _duration_ms(retry_started),
            },
        )
        return response
    except Exception as exc:
        _emit_request_event(
            on_request_event,
            "model_error",
            {
                **retry_metadata,
                "duration_ms": _duration_ms(retry_started),
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise


def _emit_request_event(
    callback: Callable[[dict[str, Any]], None] | None,
    event_type: str,
    data: dict[str, Any],
) -> None:
    if callback is None:
        return
    callback({"type": event_type, **data})


def _duration_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def open_chat_stream(
    messages: list[dict],
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout: float | None = STREAM_REQUEST_TIMEOUT_SECONDS,
) -> Stream:
    selected_model = model or MODEL
    full = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": runtime_metadata_prompt(selected_model, reasoning_effort)},
    ] + messages
    full, _ = manage_context(
        full,
        max_tokens=CONTEXT_MAX_TOKENS,
        keep_recent_messages=CONTEXT_KEEP_RECENT_MESSAGES,
        summary_max_chars=CONTEXT_SUMMARY_MAX_CHARS,
        per_message_max_chars=CONTEXT_PER_MESSAGE_MAX_CHARS,
    )
    return create_chat_completion_with_reasoning(
        model=selected_model,
        messages=full,
        stream=True,
        temperature=0.7,
        reasoning_effort=reasoning_effort,
        timeout=timeout,
    )


def stream_chat(
    messages: list[dict],
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> Iterator[str]:
    """同步流式调用 OpenAI Chat Completions，逐段 yield 文本。

    供 QThread worker 调用：阻塞迭代，UI 线程通过 signal 接收 chunk。
    """
    stream = open_chat_stream(messages, model=model, reasoning_effort=reasoning_effort)
    try:
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    finally:
        stream.close()


def generate_title(
    first_user_msg: str,
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout: float | None = TITLE_REQUEST_TIMEOUT_SECONDS,
) -> str:
    """根据首条用户消息生成会话标题（4-12 字）。"""
    try:
        resp = create_chat_completion_with_reasoning(
            model=model or MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "根据用户消息生成一个简洁的中文会话标题，4-12 个字，不要标点。",
                },
                {"role": "user", "content": first_user_msg},
            ],
            temperature=0.3,
            max_tokens=32,
            reasoning_effort=reasoning_effort,
            timeout=timeout,
        )
        title = (resp.choices[0].message.content or "").strip().strip("\"'""''")
        return title[:20] if title else "新对话"
    except Exception:
        return "新对话"
