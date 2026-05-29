# 企业级 AI Agent 服务

## 项目简介

本项目是一个可运行的企业级 AI Agent 服务：`/chat` 可通过 `AGENT_ENABLED` 启用 ReAct 编排（工具 / 短期+长期记忆 / 反思），关闭则走原直通逻辑；`/documents` 支持 txt/md/html/docx/pdf，上传后自动向量入库；Agent 可经 `knowledge_search` 调用 RAG 检索与引用生成。当前 **119 项 pytest** 连续两次全绿（覆盖率 73%、ruff 0），并已用 DeepSeek + Redis + Milvus 完成端到端验证。新增 **经营分析 Agent**：`POST /api/v1/analysis` 自然语言问数（schema → 只读 SQL → 计算 → 结论），30 题评测 **30/30**、hold-out 5/5。

架构上采用分层设计：`app/core` 承载 Agent、RAG、记忆、工具与意图能力；`app/infrastructure` 对接 **LLM 路由与熔断**、**Milvus**、**Redis**、**PostgreSQL** 与 **链路追踪**；`app/services` 提供协议适配与装配；`app/etl` 负责文档解析、分块与入库流水线。

## 架构说明

- **接入层**：`app/main.py` 创建 FastAPI 应用，`app/api/routes/` 按领域拆分路由（对话、文档、健康检查）。
- **领域核心**：`app/core/` 放置与框架无关的业务能力——Agent 图编排、RAG 管道、记忆策略、工具注册与意图识别。
- **基础设施**：`app/infrastructure/` 封装对外部系统的访问（模型网关、向量库、缓存、关系库、可观测性），便于单测与替换实现。
- **数据与 ETL**：`app/models` 定义 API/领域模型；`app/etl` 负责非结构化文档到向量索引的数据流。

部署上可通过 **Dockerfile** 构建应用镜像，**docker-compose** 一键拉起应用与依赖中间件（详见下文 Compose 说明）。

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI、Uvicorn |
| Agent / LLM | LangChain、LangGraph、OpenAI 兼容 API |
| 向量库 | Milvus（pymilvus） |
| 缓存 | Redis |
| 关系库 | PostgreSQL、SQLAlchemy |
| 配置与校验 | Pydantic v2、pydantic-settings |
| 文档处理 | unstructured、pypdf、sentence-transformers |
| 日志与韧性 | loguru、tenacity、httpx |

## 快速开始

### 本地开发

1. Python 3.11+，创建虚拟环境并安装依赖：

```bash
cd project-python
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# 也可不激活，后续命令统一使用 .\.venv\Scripts\python.exe
pip install -r requirements.txt
pip install -e .
```

2. 复制环境变量并编辑（至少填写 `OPENAI_API_KEY`；DeepSeek 可设 `OPENAI_API_BASE=https://api.deepseek.com/v1`）：

```bash
cp .env.example .env
```

3. 启动 API（需本机或 Compose 中已启动 Postgres / Redis / Milvus 若你要联调全栈）：

```bash
# Windows（推荐，免激活）
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# macOS/Linux
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

> 若本机 5432 被占用，可用 `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/agent_db` 覆盖。

4. 运行测试：

```bash
.\.venv\Scripts\python.exe -m pytest -q
```

5. 访问健康检查：<http://127.0.0.1:8000/api/v1/health>

### Docker Compose

在项目根目录准备 `.env`（可由 `.env.example` 复制），然后：

```bash
docker compose up -d --build
```

Compose 包含 **app、postgres、redis、milvus**，以及 Milvus 官方 Standalone 模式所需的 **etcd、minio**（向量与元数据存储依赖，非业务微服务）。应用默认映射 `8000` 端口。

首次启动 Milvus 可能需要数十秒就绪；若应用启动过快导致连不上 Milvus，可在生产环境中为 app 增加重试或 `depends_on` 健康检查策略。

## 目录结构说明

```
project-python/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置（pydantic-settings）
│   ├── api/routes/             # 路由：chat、document、health
│   ├── core/                   # Agent、RAG、记忆、工具、意图
│   ├── infrastructure/         # LLM、向量库、缓存、DB、追踪
│   ├── etl/                    # 解析、分块、流水线
│   └── models/                 # schemas、enums
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## 许可证

MIT（可按团队需要修改）。
