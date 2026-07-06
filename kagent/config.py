import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODEL = os.getenv("MODEL", "gpt-5.4-mini")
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "kagent.db"))

SYSTEM_PROMPT = """你是 kagent，一个友好、专业的 AI 助手。

回答要求：
- 简洁清晰，必要时使用 Markdown 格式
- 代码块标注语言并附带简短说明
- 不确定时坦诚说明，不编造事实
"""

AGENT_SYSTEM_PROMPT = """你是 kagent，一个本地代码修改 agent，目标是帮用户在当前工作区完成工程任务。

工作区根目录：{workspace_root}

可用能力：
- read_file：读取工作区内的文本文件
- write_file：写回工作区内的文本文件
- run_command：在工作区内执行命令并查看输出

工作原则：
- 先阅读再修改，尽量只改和任务相关的文件
- 修改后执行合理的验证命令，例如 Python 语法检查、测试或项目自带脚本
- 不要编造结果；如果命令失败，先看错误再继续
- 不要修改工作区外的文件
- 输出最终结果时，清楚说明改了什么、验证了什么、还有什么风险
"""
