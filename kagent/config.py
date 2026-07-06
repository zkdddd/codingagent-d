import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODEL = os.getenv("MODEL", "gpt-4o-mini")
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "kagent.db"))

SYSTEM_PROMPT = """你是 kagent，一个友好、专业的 AI 助手。

回答要求：
- 简洁清晰，必要时使用 Markdown 格式
- 代码块标注语言并附带简短说明
- 不确定时坦诚说明，不编造事实
"""
