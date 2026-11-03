# 智扫通 · 扫地机器人智能客服 Agent

面向 C 端用户的扫地机器人智能客服系统，覆盖「买前咨询 → 买后答疑 → 使用报告」全周期服务。

基于 **LangGraph ReAct Agent + RAG 检索增强** 构建：Agent 自主决定是否检索知识库、是否调用外部工具，再由大模型生成自然语言回答。

---

## 功能

### 1. 智能问答
- **售前咨询**：产品功能、价格、型号对比、选购建议
- **售后答疑**：操作指导、故障排除、耗材更换、维修保养
- 基于 RAG 从知识库检索准确片段再生成回答，避免模型凭空编造

### 2. 使用报告生成
- 读取用户使用记录（`data/external/records.csv`），分析清洁频率、耗材状态、错误日志
- 输出个性化报告与优化建议（清洁计划调整、部件更换提醒等）
- 支持用户主动查询，也可由系统定期推送

### 3. 工具调用能力
Agent 内置以下工具，由模型按需自主调用：

| 工具 | 作用 |
|---|---|
| `rag_summarize` | 检索知识库并摘要 |
| `get_weather` | 查询城市天气（高德地图 API，带 TTL 缓存） |
| `get_user_location` | 获取用户所在城市 |
| `fetch_external_data` | 按用户与月份读取使用记录 |
| `fill_context_for_report` | 切换至报告生成上下文 |
| `get_user_id` / `get_current_month` | 提供当前上下文参数 |

### 4. 会话管理
多会话持久化（SQLite），支持历史消息回溯、会话列表、Agent 调用日志查看。

---

## 技术栈

| 层次 | 技术选型 |
|---|---|
| Agent 编排 | LangGraph 1.2（ReAct 循环）、LangChain 1.4 |
| 检索增强 | Chroma 向量库 + Ollama `qwen3-embedding:4b` |
| 对话模型 | DeepSeek Chat |
| 后端 | FastAPI + Uvicorn（端口 8010） |
| 前端 | Vue 3 + TypeScript + Vite（端口 5173） |
| 容器化 | Docker（`python:3.13-slim`） |

---

## 目录结构

```
Agent/
├── agent/              # ReAct Agent 与工具集
│   ├── react_agent.py
│   └── tools/          # 知识库检索、天气、使用数据等工具
├── zsapi/              # FastAPI 后端应用
│   ├── app.py          # 路由入口
│   ├── agent_bridge.py # Agent 与 HTTP 层桥接
│   ├── insights.py     # 报告生成
│   ├── store.py        # 会话持久化
│   └── bootstrap.py    # 启动初始化
├── rag/                # 向量库构建与检索
├── prompts/            # 提示词模板
├── config/             # YAML 配置（模型、检索、天气）
├── data/               # 知识库文件（txt/pdf）与使用记录
├── chroma_db/          # 向量库持久化目录
├── web/                # Vue 3 前端工程
├── Dockerfile
└── requirements-api.txt
```

---

## 快速开始

### 1. 环境要求

- Python 3.13
- Node.js 18+
- [Ollama](https://ollama.com/)，并拉取向量模型：

```bash
ollama pull qwen3-embedding:4b
```

### 2. 启动后端

```bash
pip install -r requirements-api.txt
python -m uvicorn zsapi.app:app --host 0.0.0.0 --port 8010
```

> 注意：必须在 `Agent` 目录下执行，模块路径为 `zsapi.app:app`。

访问 `http://127.0.0.1:8010/api/health` 返回正常即启动成功。

### 3. 启动前端

```bash
cd web
npm install
npm run dev
```


> 容器内通过 `host.docker.internal:11434` 访问宿主机上的 Ollama，需确保 Ollama 已启动。前端不包含在镜像内，仍需本地 `npm run dev`。

---

## 主要接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/meta` | 服务元信息 |
| POST | `/api/chat` | 发送消息，返回 Agent 回答 |
| GET | `/api/sessions` | 会话列表 |
| POST | `/api/sessions` | 新建会话 |
| GET | `/api/sessions/{id}` | 会话详情 |
| POST | `/api/sessions/{id}/messages` | 追加消息 |
| GET | `/api/records/{user_id}` | 用户使用记录 |
| GET | `/api/records/{user_id}/{month}` | 指定月份记录 |
| GET | `/api/knowledge/stats` | 知识库统计 |
| GET | `/api/knowledge/search` | 知识库检索 |
| GET | `/api/analytics/overview` | 总览统计 |
| GET | `/api/analytics/users` | 用户维度统计 |
| GET | `/api/analytics/user/{user_id}` | 单用户统计 |
| GET | `/api/logs` | Agent 调用日志 |

---

