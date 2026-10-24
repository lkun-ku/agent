# 企业客服 Agent · 开发者指南

> 面向接手本项目的开发者。覆盖定位、技术栈、架构、环境搭建、核心模块、贡献规范、调试测试、部署与回滚。
> 当前实现是**单进程 FastAPI 服务**：RAG 问答 + Agent 工具（退款）；退款不是独立系统，也没有独立 `/refund/*` API。

## 1. 项目定位与核心目标

### 1.1 项目是什么

一个可本地运行、可容器部署的**企业客服 Agent 服务**，当前包含两条主链路：

1. **知识库问答**：文档上传/目录同步 → ETL 解析分块 → 向量化 → Milvus 检索 → DeepSeek 生成带引用的回答。
2. **退款工具**：`/chat` 识别到退款意图后，通过 Agent 工具注册中心调用 `refund` 工具；工具内部完成订单校验、规则判定、动作执行与人工转交。

### 1.2 业务价值

- 把“客服问答”和“退款处理”收进一个对话入口，避免客服在多个后台之间切换。
- 退款规则、金额、状态和台账保持确定性；LLM 只做意图/对话/政策解释，不参与金额计算。
- 退款工具可被未来其他 Agent 工具复用；新增工具不需要新增一套 API 服务。

### 1.3 适用场景

- 企业内部客服知识库 + 退款申请受理。
- 退款政策咨询、退款进度查询、人工转交。
- 面试/演示环境中的可运行 Agent 工具链样例。

### 1.4 当前非目标与边界

| 项 | 现状 |
|---|---|
| 鉴权 / RBAC / 租户隔离 | 已有 `X-API-Key` 基线；RBAC/租户隔离未实现 |
| 真实支付网关 | 提供 HTTP 适配边界；真实渠道凭证与回调/对账未接 |
| 真实订单库查询 | 已从 `refund_requests.raw_json` 恢复；上游业务库同步仍需接入 |
| 多批次退款 | 保持单 `return_id:refund` 幂等语义 |
| 人工工作台 | 工具返回 `handoff`，没有独立后台 |
| 多轮会话持久化 | 已接入 Conversation/Message；长程记忆策略未定 |
| 评测体系 | 只有 pytest 回归，没有完整离线评测平台 |

---

## 2. 技术栈全景

> 版本为 `pyproject.toml` / `requirements.txt` 中的最低要求；未锁精确补丁版本。Docker 基础镜像是 `python:3.12-slim`。

| 层 | 技术 | 版本/说明 |
|---|---|---|
| 语言 | Python | `>=3.11`；本机验证 3.12.7 |
| Web | FastAPI | `>=0.115.0` |
| ASGI | Uvicorn | `>=0.34.0` |
| 配置/校验 | Pydantic + pydantic-settings | `>=2.10` / `>=2.7` |
| LLM | OpenAI Python SDK（DeepSeek 兼容） | `>=1.60.0`；默认 `deepseek-flash` |
| 向量库 | Milvus | 客户端 `pymilvus>=2.5,<3.0`；compose 服务 `milvusdb/milvus:v2.6.25` |
| 嵌入/重排 | sentence-transformers | `>=3.3.0`；默认 `BAAI/bge-small-zh-v1.5` |
| 分词 | tiktoken | `>=0.8.0`，`cl100k_base` |
| PDF | pypdf | `>=5.0.0` |
| 数值 | NumPy | `>=2.0.0` |
| 关系库 | PostgreSQL | compose `postgres:16-alpine` |
| ORM/异步驱动 | `sqlalchemy[asyncio]` + asyncpg | `>=2.0` / `>=0.30`（含 greenlet） |
| 迁移 | Alembic | 管理公共 schema；版本 `0001_public_baseline` |
| 退款同步驱动 | psycopg2-binary | `>=2.9`；工具内同步事务 |
| 缓存/记忆 | Redis | `>=5.2`；compose `redis:7-alpine` |
| 对象存储 | MinIO | compose `minio/minio:latest`，Milvus 依赖 |
| 协调服务 | etcd | compose `quay.io/coreos/etcd:v3.5.5`，Milvus 依赖 |
| 前端 | 无独立 SPA/Node 构建 | 服务端内嵌 HTML：`/`、`/ui`、`/docs`、`/diag` |
| 日志 | loguru | stderr，支持 `LOG_JSON`；`LOG_LEVEL` 控制 |
| 追踪 | 自研 Tracer + TraceLog | `trace_id` 返回调用方；Span 持久化到 PostgreSQL |
| 指标 | prometheus-client | `/api/v1/metrics` |
| 鉴权 | FastAPI API Key 依赖 | `X-API-Key`；生产开启 |
| 容器 | Dockerfile + docker-compose | `python:3.12-slim`，单 app 容器 |
| 测试 | pytest / pytest-asyncio | `>=8.0` / `>=0.24` |
| 静态检查 | ruff / mypy | `>=0.8` / `>=1.13` |

**已移除的未使用依赖**：LangChain、LangGraph、unstructured、tenacity、python-dotenv。当前 Agent 工具层是 Python ABC + `ToolRegistry`，不是 LangGraph 图。

---

## 3. 项目架构设计

### 3.1 分层

```text
app/
├── api/routes/            # HTTP 协议层
│   ├── chat.py            # /chat /chat/stream
│   ├── document.py        # /documents/upload /documents /documents/sync-knowledge
│   ├── health.py          # /health /health/ready
│   └── web.py             # / /ui /docs /redoc /diag（服务端 HTML）
│
├── core/
│   ├── intent/recognizer.py       # 关键词意图树 + 退款动作判定 + 槽位
│   ├── tools/                     # Agent 工具层
│   │   ├── base.py                # BaseTool / ToolParameter
│   │   ├── registry.py            # register / invoke / close
│   │   ├── factory.py             # 默认工具集
│   │   └── refund/                # 退款工具（唯一退款入口）
│   ├── agent/                     # 通用 Orchestrator/Planner/ReAct/Reflection
│   ├── rag/                       # RAG 入库、检索、重排、生成
│   └── memory/                    # Redis 短期 + Milvus 长期（未接主链路）
│
├── domain/refund/         # 纯退款规则：36 字段/20 规则/15 动作/13 状态
├── etl/                   # TXT/PDF 解析、分块、流水线
├── infrastructure/
│   ├── llm/               # 模型路由、熔断、适配器
│   ├── embeddings.py      # sentence-transformers 封装
│   ├── vectordb/          # Milvus 客户端
│   ├── database/          # SQLAlchemy 模型/异步会话
│   ├── cache/             # Redis 缓存（可选）
│   └── trace/             # 内存 Tracer
├── models/                # Pydantic 请求/响应与枚举
├── config.py              # pydantic-settings
├── cli.py                 # CLI 子命令
└── main.py                # FastAPI app + lifespan
```

依赖方向不是严格六边形：`core/rag` 会直接调用 `infrastructure`；但 `domain/refund` 是纯逻辑，`core/tools/refund` 是唯一退款入口。新增功能时应优先遵守：

- 协议只放 `api/`；
- 工具放 `core/tools/`，通过 `BaseTool` + `ToolRegistry`；
- 退款规则放 `domain/refund/`，禁止 import FastAPI/DB；
- 外部适配器放 `infrastructure/`；
- 不要为单个工具新增独立服务或独立端口。

### 3.2 对话/退款数据流

```text
POST /api/v1/chat
  → ChatRequest 校验
  → IntentRecognizer.recognize()
      ├─ 售后/退款 + is_refund_action(text)=True
      │    → ToolRegistry.invoke("refund", {...})
      │       → RefundTool
      │         → AgentService
      │           → RefundService
      │             → domain/refund（校验/规则/动作/状态）
      │             → RefundStore（PostgreSQL refund schema）
      │    → ChatResponse(content=reply, tool="refund", tool_result=...)
      │
      ├─ 任务类意图 + AGENT_ORCHESTRATOR_ENABLED=true
      │    → AgentOrchestrator / ReAct
      │       → ToolRegistry（排除 refund）
      │       → ConversationMemory（只读历史）
      │    → ChatResponse(model="agent:react")
      │
      └─ 政策咨询 / 普通问答
           → Redis RAG cache
             ├─ hit → ChatResponse(..., cache_hit=true)
             └─ miss
                  → RAGPipeline.retrieve()（vector / keyword / hybrid）
                  → 可选重排 + RAGGenerator（DeepSeek）
                  → 写 Redis 缓存
                  → ChatResponse(content, citations)
                  未命中/异常 → ModelRouter 普通对话

响应返回前后：
  → Conversation/Message 持久化
  → TraceLog 持久化
```

关键点：

- 退款工具在 LLM、缓存、Orchestrator 之前执行，因此**没有 OpenAI Key 也能处理退款意图**。
- “退货政策是什么”会被 `is_refund_action()` 排除，继续走 RAG。
- 退款工具不进通用 Orchestrator 的允许工具列表，避免资金动作进入模型推理循环。
- Redis 只缓存 RAG 命中结果；退款工具永不缓存。
- `/chat/stream` 与 `/chat` 共用同一意图与工具判断，并在流结束/整段返回时持久化会话。

### 3.3 文档入库数据流

```text
knowledge/ 或 /documents/upload
  → ETLParser（TXT/PDF）
  → DocumentChunker（tiktoken 512/64，可配置策略）
  → documents/document_chunks（PostgreSQL）
  → embeddings（sentence-transformers）
  → Milvus collection
  → 查询时 retrieve + distance filter + 可选 rerank
```

### 3.4 数据存储

| 存储 | 用途 | 入口 |
|---|---|---|
| PostgreSQL `public` schema | conversations/messages/documents/document_chunks/trace_logs | `app/infrastructure/database/models.py`、`app/infrastructure/database/repositories.py` |
| PostgreSQL `refund` schema | users/orders/refund_requests/return_orders/refund_ledger/review_tasks/audit_log/kv | `migrations/001_refund_init.sql` |
| Milvus | 知识库分块向量 | `app/infrastructure/vectordb/milvus_client.py` |
| Redis | RAG 结果缓存；短期记忆为预留能力 | `app/infrastructure/cache/redis_cache.py`、`app/infrastructure/cache/factory.py` |
| 内存 | Tracer / RAG pipeline / tool registry 单例 | `app/infrastructure/trace/tracer.py`、`app/core/rag/pipeline.py`、`app/core/tools/factory.py` |

---

## 4. 本地开发环境搭建

### 4.1 前置依赖

- Python 3.11+（推荐 3.12）
- Docker Desktop / Docker Compose
- 可用 DeepSeek API Key（只跑退款工具时可暂时不配）
- 约 2–4 GB 磁盘用于嵌入模型/镜像
- Windows PowerShell 或 macOS/Linux Shell

### 4.2 安装与启动（Windows）

```powershell
cd "C:\path\to\project-python"

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

pip install -r requirements.txt
pip install -e ".[dev]"

copy .env.example .env
# 编辑 .env：至少设置 OPENAI_API_KEY；需要退款工具时设置 REFUND_ENABLED=true
```

macOS/Linux 把激活命令换成 `source .venv/bin/activate`，复制命令换成 `cp .env.example .env`。

### 4.3 启动中间件

```bash
# 只启动 PostgreSQL/Redis（不跑 RAG 时可只起 postgres）
docker compose up -d postgres redis

# 完整 RAG：PostgreSQL + Redis + etcd + MinIO + Milvus
docker compose up -d
```

如果只跑对话/退款工具、不跑知识库 RAG，可以在 `.env` 设置：

```env
RAG_ENABLED=false
```

### 4.4 初始化数据库

```powershell
# 应用表：conversations/messages/documents/document_chunks/trace_logs
python main.py init-db

# 退款工具表：独立 refund schema（REFUND_ENABLED=true 时必须）
psql "postgresql://postgres:postgres@localhost:5432/agent_db" `
  -f migrations/001_refund_init.sql
```

没有本机 `psql` 时：

```powershell
Get-Content migrations/001_refund_init.sql |
  docker compose exec -T postgres psql -U postgres -d agent_db
```

### 4.5 体检与启动

```powershell
python main.py doctor
python main.py serve
```

访问：

| 地址 | 用途 |
|---|---|
| `http://127.0.0.1:8000/` | 总览 |
| `http://127.0.0.1:8000/ui` | 聊天页 |
| `http://127.0.0.1:8000/docs` | 离线 API 文档 |
| `http://127.0.0.1:8000/api/v1/health` | 存活探针 |
| `http://127.0.0.1:8000/api/v1/health/ready` | 就绪探针（DB 不可用返回 503） |
| `http://127.0.0.1:8000/diag` | 连通性诊断 |

### 4.6 功能地图、命令与端到端验证

#### 4.6.1 HTTP 功能地图

| 方法 | 路径 | 功能 | 依赖 |
|---|---|---|---|
| GET | `/api/v1/health` | 存活探针 | 无 |
| GET | `/api/v1/health/ready` | PostgreSQL/Redis/Milvus 依赖矩阵 | PostgreSQL；Redis/Milvus 按开关 |
| GET | `/api/v1/metrics` | Prometheus 指标 | 服务自身 |
| GET | `/api/v1/version` | 应用版本与运行环境 | 服务自身 |
| GET | `/api/v1/documents` | 列出已入库文档 | PostgreSQL |
| POST | `/api/v1/documents/upload` | 上传单个 TXT/PDF/Markdown 并入库 | PostgreSQL + Milvus |
| POST | `/api/v1/documents/sync-knowledge` | 扫描 `knowledge/` 增量同步/清理 | PostgreSQL + Milvus |
| POST | `/api/v1/chat` | 统一对话入口；自动路由退款工具 / Orchestrator / RAG / LLM | RAG 需 DeepSeek/Milvus；缓存与持久化需 Redis/PG；退款工具无需 LLM |
| POST | `/api/v1/chat/stream` | SSE 流式对话；命中退款时整段返回 | 同上 |
| GET | `/`、`/ui`、`/docs`、`/diag` | 内嵌页面/离线 API 文档/诊断页 | 服务本身 |

**没有** `/api/v1/refund/*` 独立退款路由；退款只通过 `/chat` 的意图识别进入 `refund` 工具。

#### 4.6.2 CLI 功能地图

```powershell
python main.py --help                   # 查看全部命令；没有 help/chat 子命令
python main.py serve                    # 启动服务；等价于 python main.py
python main.py serve --reload           # 开发热重载
python main.py init-db                  # 初始化 public schema 应用表
uv run alembic upgrade head             # 公共 schema 版本化迁移（生产推荐）
python main.py doctor                   # 检查配置/PostgreSQL/Redis/Milvus
python main.py doctor --model --llm     # 额外检查嵌入模型和 DeepSeek

python main.py sync                     # 增量同步 knowledge/
python main.py sync --force             # 内容未变化也重建
python main.py sync --no-prune          # 不清理已删除文件
python main.py documents                # 直接查 PostgreSQL 文档表

# 下面两个命令要求服务已启动
python main.py ask "Python 基础语法有哪些"
python main.py check                    # 递归上传 --dir 文件 + 按 questions.json 判分
python main.py check --skip-upload      # 不重新上传，只跑问题清单
```

`check --dir` 已改为递归收集子目录文件；如果知识库已通过 `sync` 入库，推荐用 `check --skip-upload`，避免重复上传。

#### 4.6.3 端到端验证脚本

服务启动后按顺序验证：

```powershell
# 1. 健康与页面
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
Invoke-WebRequest http://127.0.0.1:8000/ui

# 2. 文档列表
Invoke-RestMethod http://127.0.0.1:8000/api/v1/documents

# 3. 知识库同步
Invoke-RestMethod -Method Post `
  "http://127.0.0.1:8000/api/v1/documents/sync-knowledge?force=false&prune=true"

# 4. RAG（返回 citations）
$body = @{ messages = @(@{ role = "user"; content = "Python 基础语法有哪些" }) } |
  ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/chat `
  -Method Post -ContentType "application/json" -Body $body

# 5. 退款工具：缺订单号应追问
$body = @{ messages = @(@{ role = "user"; content = "我要退款" }) } |
  ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/chat `
  -Method Post -ContentType "application/json" -Body $body

# 6. 退款工具：已有退款单号应返回幂等结果
$body = @{
  messages = @(@{ role = "user"; content = "我要退款，退款单号 RF202611100001" })
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/chat `
  -Method Post -ContentType "application/json" -Body $body
```

预期：

- RAG 回答包含 `citations`；
- 缺订单号返回 `tool_result.action = NEED_ORDER`；
- 已受理退款单返回 `DEDUPE_RETURN_EXISTING`；
- `POST /api/v1/refund/apply` 返回 `404`。

#### 4.6.4 退款工具开关

```env
REFUND_ENABLED=true      # 注册 refund 工具；false 时不注册，/chat 不处理退款动作
REFUND_SEED_DATASET=true # 仅演示/回归；把 data/refund 264 条数据 seed 进库
REFUND_SEED_DATASET=false
```

生产环境用 `REFUND_SEED_DATASET=false`，并通过业务系统写入真实 `refund_requests` / `orders`，或调用工具时传完整 `record`。

### 4.7 常见问题与排障

#### 4.7.1 同步/主键冲突

| 现象 | 处理 |
|---|---|
| `duplicate key value violates unique constraint "documents_pkey"` | 旧版本允许启动任务和 `/documents/sync-knowledge` 并发执行；当前代码已用 `asyncio.Lock` 串行化同一进程内的同步。升级后重启服务，再执行 `python main.py sync --force`。不要同时手动触发多次同步。 |
| `python main.py check` 显示“待上传 0 个文件” | 已改为递归收集 `--dir` 下的 TXT/PDF/Markdown/CSV/JSON/LOG；确认服务已启动且目录包含支持后缀。 |
| `check` 显示“未找到问题清单” | 创建 `knowledge/questions.json`，或显式传 `--questions`；没有问题清单时 `check` 只做上传验收。 |

#### 4.7.2 其他常见问题

| 现象 | 排查 |
|---|---|
| `No module named 'app'` / `openai` | 用了全局 Python；必须用 `.\.venv\Scripts\python.exe` 或先激活 `.venv` |
| `No module named 'app'` 但环境已激活 | 确认 cwd 是项目根目录，使用 `python -m pytest` 而不是裸 `pytest` |
| `init-db` 连错库 | 确认 `.env` 的 `DATABASE_URL`；CLI 已读取该配置 |
| `refund schema 未初始化` | 执行 `migrations/001_refund_init.sql`；工具不会静默建表 |
| 退款意图没有走工具 | `REFUND_ENABLED=true`；确认文本含“退款/退货/退钱/售后”等动作词 |
| “退货政策”误触发退款 | 当前由 `is_refund_action()` 排除政策/规则/流程类问法；若新增问法需同步关键词 |
| RAG 首次请求很慢 | 首次加载嵌入模型约 10–20s；之后 pipeline 单例复用 |
| RAG 不返回引用 | 检查 Milvus 是否启动、`RAG_ENABLED=true`、`RAG_MAX_DISTANCE`、集合是否为空 |
| 上传 413/415/422 | 文件超过 `MAX_UPLOAD_MB`、类型不在白名单、空文件 |
| 无法激活 venv | PowerShell 执行策略限制；改用 `.\.venv\Scripts\python.exe` 直接运行 |

---

## 5. 核心功能模块

### 5.1 应用入口与生命周期

- 入口：`app/main.py`
- `create_app()`：注册 health/chat/document/web 路由；退款**不注册独立路由**。
- `lifespan`：初始化 SQLAlchemy 引擎、会话工厂、知识库自动扫描、`ToolRegistry`；关闭时释放工具连接池、Redis 缓存和数据库引擎。
- 启动命令：`python main.py serve`（`main.py` 是 CLI 的薄入口）。

### 5.2 对话入口

- 文件：`app/api/routes/chat.py`
- 路由：`POST /api/v1/chat`、`POST /api/v1/chat/stream`
- 逻辑：
  1. `IntentRecognizer.recognize()`；
  2. `_try_refund()`：退款意图 → `ToolRegistry.get_tool("refund")` → `RefundTool.execute()`；
  3. 任务类意图 → `_try_orchestrator()` → `AgentOrchestrator / ReAct`；
  4. 政策/普通问答 → Redis RAG 缓存 → `_try_rag()`；未命中/异常回退 `ModelRouter.chat()`；
  5. 返回 `ChatResponse`（`conversation_id` / `tool` / `tool_result` / `citations` / `cache_hit`）；
  6. 响应路径持久化 `Conversation` / `Message`，并把内存 Span 写入 `TraceLog`。
- 退款命中时不需要 `OPENAI_API_KEY`；任务编排、RAG 生成、普通对话需要。
- 持久化失败只记录 warning，不影响聊天可用性。

### 5.3 意图识别

- 文件：`app/core/intent/recognizer.py`、`app/core/intent/semantic.py`
- 类型：**混合方案**——强规则优先 + 本地 BGE 语义近邻兜底 + 低置信度澄清。
- 规则层：树形关键词、子意图和槽位抽取；命中强特征时零额外模型开销。
- 语义层：规则置信度不足时，用本地嵌入模型对少量高代表性语句做最近邻分类；相似度低于 `INTENT_SEMANTIC_MIN_SIMILARITY` 不采纳。
- 资金闸门：`is_refund_action()` 独立于意图标签；即使语义分类器认为是售后，也必须通过该闸门并满足单号/动作特征才会调用退款工具。
- 政策咨询：`退货政策是什么`、`退款流程怎么走` 归类为 `问答/政策咨询`，继续走 RAG，不误触发退款。
- 槽位：`order_id`、`refund_id`、`numbers`、`raw_query`。
- 结果来源：`IntentResult.source` 标记 `rule` / `semantic` / `fallback`，便于影子评估与排障。

### 5.4 Agent 工具层

| 文件 | 职责 |
|---|---|
| `app/core/tools/base.py` | `BaseTool`、`ToolParameter`、OpenAI tools 风格参数 schema、工具生命周期 |
| `app/core/tools/schemas.py` | `ToolResult / RefundToolResult / ToolHandoff` 统一工具出参 |
| `app/core/tools/registry.py` | 注册、按名获取、类型化 `invoke()`、关闭资源 |
| `app/core/tools/factory.py` | 懒加载默认工具；`REFUND_ENABLED` 决定是否注册 `refund` |
| `app/core/tools/refund/tool.py` | `RefundTool`：参数校验、懒加载服务、统一错误回复 |
| `app/core/tools/refund/agent_service.py` | 把内部结果映射为 `AgentResponse`（不依赖 HTTP） |
| `app/core/tools/refund/service.py` | 退款编排：受理、幂等、状态、人工任务 |
| `app/core/tools/refund/nodes.py` | 15 个动作节点 |
| `app/core/tools/refund/store.py` | PostgreSQL `refund` schema 适配器 |
| `app/core/tools/refund/payment.py` | `SimulatedPaymentGateway`，生产替换为真实网关 |
| `app/core/tools/refund/ports.py` | `RefundStore` / `PaymentGateway` 协议 |
| `app/core/tools/refund/schemas.py` | `AgentRequest/AgentResponse/TaskView` |

新增工具步骤：

1. 继承 `BaseTool`，实现 `async execute(**kwargs)`；
2. 在 `factory.get_tool_registry()` 注册；
3. 不要新增独立 HTTP 服务；由 Agent 入口按意图/模型调度。

### 5.5 退款领域内核

- 目录：`app/domain/refund/`
- 内容：
  - `contracts.py`：36 字段契约、枚举、阈值、动作标签；
  - `activities/ingest.py`：字段校验；
  - `activities/eligibility.py`：准入检查；
  - `activities/risk.py`：20 条规则；
  - `activities/dispatch.py`：15 个动作的优先级。
- 纯逻辑，不依赖 FastAPI/DB/LLM。
- 当前退款流程：受理 → 准入 → 风控 → 动作 → 状态/台账/人工任务；真实资金执行仍为模拟。

### 5.6 共享工具集

- 目录：`app/shared/`
- 约束：只允许纯函数、常量与轻量类型；禁止 FastAPI/SQLAlchemy/Redis/Milvus/OpenAI 依赖。
- 已提供：
  - `jsonx.py`：JSON 序列化与容错解析；
  - `hashing.py`：SHA-256、UUIDv4、UUIDv5；
  - `times.py`：UTC 时间、保留期截止点、诊断时间；
  - `files.py`：上传文件名清理与类型白名单；
  - `http.py`：SSE 帧编码。
- 详细清单见 `app/shared/README.md`。

### 5.7 RAG 与文档

| 文件 | 职责 |
|---|---|
| `app/core/rag/pipeline.py` | `RAGPipeline`：索引/检索/生成；`get_pipeline()` 进程单例 |
| `app/core/rag/ports.py` | `DocumentIndexingService` 与知识同步的最小 Pipeline 端口 |
| `app/core/rag/ingest.py` | `knowledge/` 增量同步、sha256 变更检测、回填/清理 |
| `app/core/rag/store.py` | Milvus 分块读写、先删后插、检索 |
| `app/core/rag/search.py` | 中文 BM25 与 RRF 检索内核 |
| `app/core/rag/indexing.py` | 上传与同步共用的 ETL → DB → 向量库生命周期 |
| `app/core/rag/reranker.py` | CrossEncoder 重排（可选） |
| `app/core/rag/generator.py` | 上下文拼装、引用解析、`RAGResponse` |
| `app/etl/` | TXT/PDF 解析、tiktoken 递归分块、流水线 |
| `app/api/routes/document.py` | 上传、列表、知识库同步；类型/体积/空文件校验 |
| `app/api/routes/health.py` | 存活/就绪探针 |
| `app/api/routes/web.py` | 服务端 HTML 页面与离线文档路由 |
| `app/static/` | 内置页面 HTML/CSS/JS 资源 |

### 5.8 通用 Agent / 会话记忆

### 5.8 通用 Agent / 会话记忆

- `app/core/agent/`：仅保留生产使用的 `AgentOrchestrator` 与 `ReActAgent`。
- `app/api/routes/chat.py`：任务类意图在 `AGENT_ORCHESTRATOR_ENABLED=true` 时进入 ReAct。
- 未接线的 memory、Planner、Reflection、MultiRetriever 与 Redis 语义缓存已删除，避免概念重复。
- `app/core/agent/adapters.py`：把 `ToolRegistry`、`ModelRouter`、`Tracer` 适配成通用 Agent 所需端口。
- `app/infrastructure/database/repositories.py`：`ConversationMemory` 提供只读最近历史；完整一轮问答仍由 `/chat` 统一写入。
- 退款意图不进入通用 Orchestrator；始终走确定性退款工具。

### 5.9 基础设施

- `app/infrastructure/llm/model_router.py`：优先级/权重路由、熔断、降级、thinking 参数。
- `app/infrastructure/llm/circuit_breaker.py`：closed/open/half-open。
- `app/infrastructure/embeddings.py`：sentence-transformers 封装，懒加载。
- `app/infrastructure/vectordb/milvus_client.py`：集合创建/插入/检索/删除。
- `app/infrastructure/database/`：SQLAlchemy 模型、异步会话、会话/Trace 仓储。
- `app/infrastructure/trace/tracer.py`：内存 span，`/chat` 返回 `trace_id`。
- `app/infrastructure/observability/`：trace context、Prometheus 指标；HTTP 中间件记录 QPS/延迟/错误。
- `/api/v1/metrics`：Prometheus 抓取端点。
- `/api/v1/health/ready`：PostgreSQL/Redis/Milvus 依赖矩阵；PostgreSQL 是关键依赖。
- `/api/v1/version`：应用版本与运行环境。
- `LOG_JSON=true` 输出结构化日志，采集系统可直接解析。
- `TRACE_LOG_RETENTION_DAYS` / `CONVERSATION_LOG_RETENTION_DAYS` 控制排障数据保留期；Trace payload 会脱敏常见凭据字段。
- `app/infrastructure/cache/factory.py` + `redis_cache.py`：RAG 结果缓存，已接 `/chat` 主链路。

### 5.9 CLI

- `app/cli.py`，由根目录 `main.py` 转发：
  - `serve`、`init-db`、`sync`、`doctor`、`check`、`ask`、`documents`。
- `init-db` 只建应用表；退款 schema 必须单独执行 `migrations/001_refund_init.sql`。

---

## 6. 代码规范与贡献指南

### 6.1 代码规范

- Python 3.11+，全量类型标注；公共函数写 docstring。
- 行宽 100；`ruff check app tests` 必须通过。
- `mypy app` 必须通过；`pyproject.toml` 已开启 `strict = true`。不允许用 `# type: ignore` 掩盖真实类型错误。
- 使用 `uv.lock` 固化依赖；修改依赖后运行 `uv lock` 并提交锁文件。
- 本地提交建议安装 pre-commit；CI 会执行 ruff、mypy 和带覆盖率的 pytest。
- 领域层 `app/domain/refund` 禁止 import `fastapi`、`sqlalchemy`、`psycopg2`、`app.infrastructure`。
- 新工具统一放 `app/core/tools/`，实现 `BaseTool`，在 `factory.py` 注册。
- 禁止为退款新增 `/refund/*` 路由、独立服务或独立数据库；退款只能由 Agent 工具调用。
- 新增外部依赖前先确认现有依赖能覆盖；不要重新引入 LangChain/LangGraph（当前未使用）。
- 数据库变更必须提供 `migrations/00X_*.sql`，不要只改 ORM 让 `create_all` 猜。

### 6.2 分支管理

```text
main                 # 可运行、测试通过
feat/<topic>         # 新功能
fix/<topic>          # 修复
refactor/<topic>     # 不改变行为的重构
docs/<topic>         # 文档
chore/<topic>        # 依赖/构建/清理
```

- 一个分支只做一类变更；不要把退款规则、部署配置、文档混在一个 PR。
- 合并前 rebase/merge `main`，解决冲突后再跑门禁。

### 6.3 提交格式

采用 Conventional Commits：

```text
feat(refund): route refund intent to agent tool
fix(cli): honor DATABASE_URL in init-db
refactor(tools): move refund workflow under core/tools/refund
test(refund): cover intent-to-tool routing
docs: replace legacy design docs with developer guide
chore(deps): remove unused LangChain packages
```

要求：

- 标题 ≤72 字符，动词开头；
- 正文写“为什么”和“影响范围”；
- 不提交 `.env`、密钥、上传文件、`__pycache__`、覆盖率产物。

### 6.4 PR 流程

1. 从 `main` 建分支；
2. 先写/更新测试，再改实现；
3. 跑 `ruff check app tests`、`mypy app --strict`、`pytest -q`；
4. 数据库变更附迁移文件与回滚说明；
5. 配置项变更同步 `.env.example` 和本指南；
6. PR 描述包含：背景、改动、测试证据、风险/回滚；
7. 至少一名 reviewer 通过后合并；合并后删除分支。

---

## 7. 调试与测试

### 7.1 测试命令

```powershell
# 全量
python -m pytest -q

# 退款工具、意图、路由、264 条动作
python -m pytest -q tests/refund

# 只跑需要真实 PostgreSQL 的集成用例（无 PG 自动 skip）
python -m pytest -q -m integration
```

当前基线：`143 passed`，其中退款相关 12 条；`ruff` 与 `mypy --strict` 通过；应用覆盖率约 `66%`。

测试目录：

```text
tests/
├── test_cli.py / test_document.py / test_ingest.py
├── test_memory.py / test_model_router.py / test_planner.py
├── test_p1_p3.py / test_phase1.py / test_phase3.py
├── test_rag_pipeline.py / test_retriever.py / test_retry_policy.py
├── test_schema_validation.py / test_rag_validation.py / test_web.py
└── refund/
    ├── test_dataset.py        # 264 条动作一致
    ├── test_service.py        # 批量/人工路径
    ├── test_tool.py           # 工具 & 意图 & /chat 调用链
    ├── test_routing.py        # 无独立 /refund 路由
    ├── test_postgres_store.py # 真实 PG 适配器
    └── sqlite_store.py        # 测试 double（不进入生产）
```

### 7.2 日志与追踪

- 日志：loguru 输出到 stderr；级别由 `LOG_LEVEL` 控制，`LOG_JSON=true` 输出结构化 JSON，并自动绑定 `trace_id` / `conversation_id`。
- 请求追踪：`/chat` 返回 `trace_id`；`Tracer` 记录子 Span，并持久化到 `trace_logs`。
- 指标：`/api/v1/metrics` 暴露 HTTP QPS/延迟/错误、chat 模式分布、RAG cache hit/miss 与依赖错误计数。
- 保留策略：`trace_logs` 默认保留 30 天，`messages` 默认保留 90 天。
- 健康/诊断：
  - `/api/v1/health`：存活；
  - `/api/v1/health/ready`：PostgreSQL 就绪；
  - `/diag`：服务、代理、Milvus 等连通性页面；
  - `python main.py doctor`：配置/DB/Redis/Milvus/模型体检。
- 退款排查：看 `tool_result.status/action/queue/reason`；没有独立退款日志文件。
- RAG 排查：日志会打印 top1/top2 距离与阈值；距离大于 `RAG_MAX_DISTANCE` 视为未命中。

### 7.3 常见调试手段

```powershell
# 直接问一条
python main.py ask "退款政策是什么"

# 只测意图
python -c "import asyncio; from app.core.intent.recognizer import IntentRecognizer; print(asyncio.run(IntentRecognizer().recognize('我要退款')))"

# 只测工具（需要已 seed 或传入完整 record）
python -c "import asyncio; from app.core.tools import get_tool_registry; print(asyncio.run(get_tool_registry().invoke('refund', {'refund_id':'RF...'})))"
```

---

## 8. 部署流程

### 8.1 构建与启动

```bash
docker compose build app
docker compose up -d
```

`docker-compose.yml` 当前启动：`app + postgres + redis + etcd + minio + milvus`。仅聊天/退款可只起 `postgres`，并设置 `RAG_ENABLED=false`。

> 容器内 RAG 需要可访问的嵌入/重排模型。若 `EMBEDDING_MODEL`/`RERANKER_MODEL` 指向宿主机路径，必须把模型目录挂载进容器并改成容器内路径；否则 RAG 检索会降级为普通对话。

### 8.2 数据库初始化（生产同样适用）

```bash
# 应用表（幂等）
docker compose run --rm app python main.py init-db

# 退款 schema（REFUND_ENABLED=true 时必须）
docker compose exec -T postgres psql -U postgres -d agent_db \
  < migrations/001_refund_init.sql
```

应用启动不会自动建表；迁移是显式步骤。建议在发布流水线中先迁移、再滚动启动。

### 8.3 关键配置

| 变量 | 作用 | 生产建议 |
|---|---|---|
| `DATABASE_URL` | PostgreSQL DSN | 使用密钥管理；compose 内主机名为 `postgres` |
| `DATABASE_CONNECT_TIMEOUT` | PostgreSQL 建连超时秒数 | 默认 5 |
| `DATABASE_COMMAND_TIMEOUT` | PostgreSQL 命令超时秒数 | 默认 30 |
| `DATABASE_POOL_SIZE` | 异步连接池常驻连接数 | 默认 10 |
| `DATABASE_MAX_OVERFLOW` | 异步连接池最大溢出连接数 | 默认 10 |
| `REDIS_URL` | Redis | 与 compose 服务名一致 |
| `REDIS_SOCKET_TIMEOUT` | Redis 读写超时秒数 | 默认 5 |
| `REDIS_SOCKET_CONNECT_TIMEOUT` | Redis 建连超时秒数 | 默认 5 |
| `REDIS_HEALTH_CHECK_INTERVAL` | Redis health check 间隔秒数 | 默认 30 |
| `MILVUS_TIMEOUT` | Milvus SDK 超时秒数 | 默认 10 |
| `MILVUS_HOST/PORT` | Milvus | compose 内为 `milvus:19530` |
| `OPENAI_API_KEY` | DeepSeek Key | 注入 Secret，不入库/不入镜像 |
| `OPENAI_MODEL` | 模型名 | 固定版本，避免行为漂移 |
| `RAG_ENABLED` | 是否检索增强 | 无 Milvus 时设 `false` |
| `RAG_RETRIEVAL_MODE` | `vector` / `keyword` / `hybrid` | 生产按评测选择，默认 `hybrid` |
| `RAG_CACHE_ENABLED` | 是否缓存 RAG 命中结果 | 默认 `true`；退款不缓存 |
| `RAG_CACHE_TTL_SECONDS` | RAG 缓存 TTL | 默认 3600；知识库更新后自然过期 |
| `CONVERSATION_PERSISTENCE_ENABLED` | 是否写会话/消息 | 默认 `true`；无状态压测可关闭 |
| `TRACE_PERSISTENCE_ENABLED` | 是否写 TraceLog | 默认 `true`；高流量可采样后开启 |
| `AGENT_ORCHESTRATOR_ENABLED` | 是否启用任务类 ReAct | 默认 `true`；退款不走该开关 |
| `AGENT_MAX_STEPS` | ReAct 最大步数 | 默认 8，防止循环 |
| `API_AUTH_ENABLED` | 是否要求 `X-API-Key` | 生产必须 `true` |
| `API_KEY` | 内部 API Key | Secret 管理，不入库不入镜像 |
| `PAYMENT_GATEWAY_MODE` | `simulated` / `http` | 生产必须 `http` 并接入真实渠道 |
| `PAYMENT_GATEWAY_URL` | HTTP 支付网关退款接口 | 生产必填 |
| `PAYMENT_GATEWAY_TOKEN` | HTTP 支付网关 Token | Secret 管理 |
| `PAYMENT_GATEWAY_TIMEOUT` | 支付网关超时秒数 | 默认 5 |
| `REFUND_ENABLED` | 是否注册退款工具 | 默认 `false`；灰度时再开 |
| `REFUND_SEED_DATASET` | 是否 seed 264 条演示数据 | 生产必须 `false` |
| `LOG_LEVEL` | 日志级别 | `INFO`，排障临时 `DEBUG` |
| `LOG_JSON` | 是否 JSON 结构化日志 | 生产采集建议 `true` |
| `TRACE_LOG_RETENTION_DAYS` | TraceLog 保留天数 | 默认 30 |
| `CONVERSATION_LOG_RETENTION_DAYS` | 会话消息保留天数 | 默认 90 |

`docker-compose.yml` 已透传鉴权、支付网关、会话持久化、TraceLog、RAG 缓存、检索模式、Orchestrator 与退款开关；新增配置时同步 `.env.example` 和 compose。

### 8.4 健康检查

- Dockerfile 已配置 `HEALTHCHECK`，命中 `/api/v1/health`。
- 编排层应同时检查 `/api/v1/health/ready`（PostgreSQL）。
- 退款工具首次调用才建 PG 连接池；若迁移缺失会直接返回工具错误，不会静默建表。

### 8.5 版本回滚

1. **应用回滚**：保留上一版镜像 tag/digest，`docker compose down` 后用旧镜像启动；不要覆盖旧 tag。
2. **退款开关**：紧急情况设置 `REFUND_ENABLED=false`，聊天与 RAG 不受影响；已产生的退款台账保留。
3. **public schema**：使用 `uv run alembic downgrade` 前必须备份数据；生产推荐向前修复。
4. **refund schema**：迁移只有向前版本（001、002…），没有自动 down；回滚前先备份 PostgreSQL，不要 `DROP SCHEMA refund`。
5. **配置回滚**：`.env`/Secret 版本化；回滚时同时恢复模型名、开关与数据库 DSN。
6. **验证**：回滚后跑 `/health/ready`、`python main.py doctor`、`pytest -q`（或对应 smoke）。

### 8.6 生产未完成项

- RBAC/租户/限流；API Key 只是第一层基线；
- 真实支付网关与回调、退款对账；HTTP 适配器只是边界，不是已接入渠道；
- 上游业务订单库同步与更完整的退款单 repository；
- 人工工作台、SLA、通知；
- 多租户隔离、审计留存、PII 加密；
- 观测平台/告警/链路持久化、CI/CD 与压测。

在这些项完成前，当前服务适合内部演示/预发，不应直接承载真实资金。
