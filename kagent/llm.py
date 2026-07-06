from typing import Iterator

from openai import OpenAI

from .config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL, SYSTEM_PROMPT

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


def stream_chat(messages: list[dict]) -> Iterator[str]:
    """同步流式调用 OpenAI Chat Completions，逐段 yield 文本。

    供 QThread worker 调用：阻塞迭代，UI 线程通过 signal 接收 chunk。
    """
    full = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    stream = client.chat.completions.create(
        model=MODEL,
        messages=full,
        stream=True,
        temperature=0.7,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


def generate_title(first_user_msg: str) -> str:
    """根据首条用户消息生成会话标题（4-12 字）。"""
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "根据用户消息生成一个简洁的中文会话标题，4-12 个字，不要标点。",
                },
                {"role": "user", "content": first_user_msg},
            ],
            temperature=0.3,
            max_tokens=32,
        )
        title = (resp.choices[0].message.content or "").strip().strip("\"'""''")
        return title[:20] if title else "新对话"
    except Exception:
        return "新对话"
