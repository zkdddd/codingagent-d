# kagent

最小化对话智能体桌面版 — PyQt6 单体应用，类似 codex 的本地软件形态。

## 功能

- 桌面 GUI（非网页），原生窗口
- 流式多轮对话（OpenAI Chat Completions）
- 多会话管理（侧边栏切换 / 新建 / 自动标题）
- 会话历史持久化（SQLite）
- Markdown 渲染 + 代码高亮
- 后台线程流式（UI 不卡顿）

## 技术栈

- **UI**：PyQt6（QThread 后台流式 + signal 推送主线程）
- **LLM**：OpenAI Python SDK（同步流式）
- **存储**：sqlite3 标准库（无需额外依赖）
- **Markdown**：markdown + pygments

## 快速开始

### 1. 安装依赖

```bash
cd D:/kd/pyproject/kagent
pip install -r requirements.txt
```

### 2. 配置 API

`.env` 已生成（基于 `.env.example`），如需修改 key 或换代理服务，编辑 `.env`：

```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://jp-api.zhexueqi.xyz/v1
MODEL=gpt-5.5
DB_PATH=./kagent.db
```

### 3. 启动

```bash
python main.py
```

## 项目结构

```
kagent/
├── kagent/
│   ├── __init__.py
│   ├── config.py            # 配置加载
│   ├── db.py                # SQLite 同步访问
│   ├── llm.py               # OpenAI 流式封装
│   └── ui/
│       ├── chat_worker.py   # QThread 流式 worker
│       ├── main_window.py   # 主窗口 + 侧边栏 + 输入区
│       └── markdown_view.py # Markdown 渲染 + 代码高亮
├── main.py                  # 入口
├── requirements.txt
├── .env.example
└── README.md
```

## 关键设计

### 1. QThread + Signal 流式架构
后台线程阻塞迭代 OpenAI stream，每个 chunk 通过 `pyqtSignal` 投递到主线程更新 UI，避免界面卡顿。

### 2. 单体应用（无 HTTP 服务层）
PyQt6 进程直接调用 OpenAI SDK，省去 FastAPI 中间层。后续若需 Web 端，可独立抽出 API 层。

### 3. 同步 SQLite
PyQt 与 asyncio 集成需要 qasync 等额外库，增加复杂度。改用标准库 `sqlite3` + `threading.Lock`，简洁稳定。

### 4. 流式块整页重渲染
每次 chunk 到达时，从 DB 取已完成消息 + 当前流式缓冲，整体重新渲染。代码简单，1000 字以内无明显性能问题。

## 常见问题

**Q: 启动报错 `Connection error`**
A: 检查 `.env` 中 `OPENAI_BASE_URL` 是否正确，末尾需带 `/v1`。

**Q: 模型名报错 `model not found`**
A: 代理服务支持的模型名与官方不同，确认 `MODEL` 与代理方文档一致。

**Q: PyQt6 启动闪退无报错**
A: 在命令行运行 `python main.py`，stderr 会打印堆栈。

## 下一步

- [ ] 长期记忆系统（mem0 风格，跨会话事实抽取）
- [ ] MCP 工具调用（搜索 / 文件 / 代码沙箱）
- [ ] RAG 知识库（文档上传 + 向量检索）
- [ ] 多智能体编排（LangGraph 风格）
- [ ] 系统托盘 + 全局快捷键
