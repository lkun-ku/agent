# 企业客服 Agent

一个可本地运行、可容器部署的客服 Agent 服务：**FastAPI + DeepSeek + Milvus + PostgreSQL**。

当前提供两条主链路：

1. **知识库问答**：文档上传/目录同步 → 解析分块 → 向量检索 → 带引用回答。
2. **退款工具**：`/chat` 识别退款意图后，通过 `ToolRegistry` 调用 `refund` 工具；退款不是独立系统，没有独立 `/refund/*` API。

完整的模块、架构、测试、部署与回滚说明见 **[docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md)**。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev]"

copy .env.example .env
# 编辑 .env：配置 OPENAI_API_KEY；需要退款工具时设 REFUND_ENABLED=true
```

```powershell
docker compose up -d postgres redis
python main.py init-db
uv run alembic upgrade head
python main.py doctor
python main.py serve
```

需要 RAG 时启动完整中间件：

```powershell
docker compose up -d
```

退款工具需要额外执行：

```powershell
psql "postgresql://postgres:postgres@localhost:5432/agent_db" `
  -f migrations/001_refund_init.sql
```

浏览器访问 `http://127.0.0.1:8000/ui`；API 文档 `http://127.0.0.1:8000/docs`。

## 结构

```text
app/api/routes/        # HTTP：chat / documents / health / web
app/core/intent/       # 意图识别（含退款动作判定）
app/core/tools/        # Agent 工具层；refund/ 为退款工具
app/domain/refund/     # 退款纯规则
app/core/rag/          # RAG 检索与生成
app/etl/               # 文档解析与分块
app/infrastructure/    # LLM / 向量库 / DB / Redis / Trace
app/main.py            # FastAPI 入口
```

## 质量门禁

```powershell
uv sync --extra dev
uv run ruff check app tests
uv run mypy app
uv run pytest -q --cov=app --cov-report=term-missing
```

当前基线：`128 passed`，其中退款相关 12 条；`mypy --strict` 通过；应用覆盖率约 `63%`；已接入 Alembic、API Key、Prometheus 指标、JSON 日志、依赖健康矩阵、Trace 保留策略和 HTTP 支付网关适配。

## 许可

MIT
