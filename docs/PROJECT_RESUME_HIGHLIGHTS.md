# Enterprise AI Agent · 项目简历素材

> 本文件只整理**本项目当前已经实现、可演示、可测试**的能力，供简历撰写和面试复盘使用。  
> 生成时间：2026-11-14。  
> 原则：**不写没用过的框架，不编造未测指标；没有硬指标的地方明确标注“待补测”。**

---

## 一、项目一句话定位

**Enterprise AI Agent：一个面向客服与知识库场景的生产风格 Agent 服务，使用 FastAPI + DeepSeek + Milvus + PostgreSQL 实现可引用 RAG、确定性退款工作流、ReAct 工具编排、运营后台与可观测性。**

它不是单纯的 Prompt Demo，而是围绕三条主链路做的工程化项目：

1. **知识库问答链路**：文档入库 → 混合检索 → 重排 → 带引用生成 → 缓存 / 降级 / 流式输出；
2. **自动化退款链路**：意图识别 → 退款工具 → 风控规则 → 状态机 → 模拟支付 → 台账 / 审计 / 人工任务；
3. **运营与观测链路**：退款运营后台、健康检查、Prometheus 指标、TraceLog、结构化日志。

---

## 二、项目体量

当前真实规模如下，可直接用于简历概述或面试口径：

| 维度 | 数据 |
|---|---:|
| 应用 Python 文件 | 93 个 |
| 应用 Python 行数 | 约 8,676 行 |
| 测试文件 | 25 个 |
| 测试代码行数 | 约 2,214 行 |
| 自动化测试 | 149 passed |
| PostgreSQL 集成测试 | 2 passed |
| 应用覆盖率 | 约 66% |
| 静态检查 | Ruff 通过 |
| 类型检查 | Mypy `--strict` 通过，93 files 无问题 |
| API 路径 | 13 个 OpenAPI path |
| 知识库文件 | 22 份 |
| 知识库分块 | 1,136 块 |
| 退款测试场景 | 14 个 |
| 退款风控规则 | 20 条 |
| 退款工作流状态 | 13 个 |

项目定位建议写成：

> **可容器部署的生产风格客服 Agent 原型**，而非已经承载真实企业生产流量的系统。这样既体现代码深度，也不会在面试中被误判为过度包装。

---

## 三、简历项目概述模板

### 版本 A：中文简历，偏 AI 应用 / Agent 方向

```text
项目名称：Enterprise AI Agent · 可引用知识库问答与确定性退款工作流
技术栈：Python / FastAPI + SSE / asyncio / DeepSeek / Milvus + bge-large-zh-v1.5 /
       PostgreSQL + SQLAlchemy 2.0 async / Redis / Alembic / Prometheus / pytest

项目介绍：
面向客服与知识库场景的可容器部署 Agent 服务。系统将 22 份资料、1,136 个分块接入 Milvus，
支持带 [n] 引用的 RAG 问答、资料不足拒答、退款工单确定性处理、人工任务与运营后台；退款
流程不交给 LLM 生成，而由 20 条规则、13 个状态机和 PostgreSQL 台账保证幂等与可审计。

个人工作：
● 设计 hybrid RAG 链路：bge-large 向量召回 + 中文 BM25 + RRF 融合 + CrossEncoder 重排，
  结合 Redis 结果缓存与未命中降级，实现可引用答案、SSE 流式输出与依赖异常下的服务降级。
● 构建确定性退款工作流：14 类场景、20 条风控规则、13 个状态流转、幂等台账、人工任务、
  审计日志与模拟支付网关适配，避免把资金动作交给 LLM 生成。
● 抽取 shared 纯函数工具层与 RAG Pipeline 端口，统一 BM25/RRF、JSON、哈希、UUID、SSE、
  时间和文件校验逻辑，减少跨层重复实现并防止基础设施反向污染领域层。
● 搭建退款运营后台 /ops/refunds：提交订单快照后实时查看动作、金额、规则命中、风险等级、
  台账状态、人工任务和全局统计，使退款链路从“黑盒调用”变成可运营验证。
● 完善生产化门禁：149 个自动化测试、PostgreSQL 集成测试、覆盖率约 66%、Ruff 通过、
  Mypy strict 通过、Prometheus 指标、JSON 日志、TraceLog、依赖健康矩阵与 Alembic 迁移。
```

### 版本 B：英文简历，偏 Python / AI Backend 方向

```text
Enterprise AI Agent — Retrieval-augmented customer-service Agent with deterministic refund workflow
Stack: Python, FastAPI, SSE, asyncio, DeepSeek, Milvus, bge-large-zh-v1.5, PostgreSQL,
SQLAlchemy 2.0 async, Redis, Alembic, Prometheus, pytest

Built a containerized customer-service Agent that ingests 22 documents / 1,136 chunks into
Milvus and serves citation-grounded RAG answers with streaming output, cache fallback and
dependency health checks.

Designed a deterministic refund workflow with 20 risk rules, 13 workflow states, idempotent
ledger entries, audit logs and manual-review tasks, ensuring refund actions are not generated
by an LLM.

Refactored the codebase into a shared utility layer and RAG pipeline port, unifying BM25/RRF,
JSON, hashing, UUID, SSE, time and file-validation logic across API, CLI, domain and
infrastructure layers.

Delivered an operations console for submitting refund orders and inspecting actions, amounts,
rule hits, risk tier, ledger state, audit transitions and pending tasks.

Established quality gates with 149 automated tests, PostgreSQL integration tests, ~66% app
coverage, Ruff, mypy --strict, Prometheus metrics, structured JSON logs and Alembic migrations.
```

---

## 四、核心亮点拆解

### 亮点 1：RAG 不是“向量搜索调用”，而是完整混合检索链路

**做了什么：**

- 支持 TXT / PDF / Markdown / CSV / LOG 等多格式解析；
- 使用 tiktoken 递归分块；
- 向量库使用 Milvus，embedding 使用 `bge-large-zh-v1.5`；
- 检索使用：
  - 向量召回；
  - 中文 BM25；
  - RRF 融合；
  - 可选 CrossEncoder 重排；
- 生成阶段要求模型基于上下文作答，并解析 `[1]`、`[2]` 引用；
- Redis 结果缓存命中时直接返回；
- RAG 异常或未命中时降级普通 LLM 对话；
- 提供 SSE 流式输出。

**简历写法：**

```text
Built a hybrid RAG pipeline using Milvus, bge-large-zh-v1.5, Chinese BM25 and RRF fusion with
optional CrossEncoder reranking; generated citation-grounded answers with Redis caching, SSE
streaming and graceful fallback for retrieval or LLM failures.
```

**面试追问可以讲：**

1. 为什么不用纯向量检索？  
   因为中文政策类问题中，订单号、状态、金额、专有名词对精确匹配敏感，BM25 能补足关键词召回。

2. RRF 的作用是什么？  
   把向量检索和 BM25 的排名结果按倒数排名融合，避免两路分数直接相加导致的量纲问题。

3. 为什么加重排？  
   混合检索的候选量比最终 Top K 大，CrossEncoder 用更重的交叉注意力模型对 query-chunk 重新打分，提高最终答案上下文相关性。

4. 如何避免幻觉？  
   Prompt 明确要求只依据上下文作答；上下文编号会写入 Prompt；生成后解析引用；知识库未命中时降级普通对话或明确提示。

---

### 亮点 2：退款链路“确定性优先”，LLM 不做资金决策

**做了什么：**

- 用户退款意图通过规则识别后，不进入 RAG / LLM，直接路由到 `refund` 工具；
- 退款由规则层处理，不依赖模型自由发挥；
- 实现 20 条风控规则；
- 使用 13 个工作流状态；
- 支持 14 类退款场景；
- PostgreSQL `refund` schema 保存订单、退款单、状态机、台账、人工任务、审计日志；
- 通过幂等键防止重复退款；
- 支付网关抽象成 Port，当前使用模拟网关，生产可替换为 HTTP 真实渠道。

**简历写法：**

```text
Designed a deterministic refund workflow with 20 risk rules, 13 workflow states and 14 test
scenarios; implemented idempotent ledger entries, audit transitions, manual-review tasks and a
simulated payment gateway port to prevent LLM-driven financial decisions.
```

**为什么这是亮点：**

很多 Agent 项目会把退款、支付、工单这类高风险动作全部交给 Function Calling + LLM。  
这个项目反过来，把 LLM 只用于理解用户输入，资金动作交给规则和状态机，这是更符合生产设计的取舍。

**面试追问可以讲：**

1. 为什么不让 LLM 判断是否退款？  
   因为资金动作要求可解释、可回放、可审计。LLM 输出不稳定，不能作为唯一裁决依据。

2. 怎么保证不重复退款？  
   使用 `refund_id` / `idempotency_key` 查找已有售后单；已处理单会返回 `DEDUPE_RETURN_EXISTING`；台账使用 `return_id:refund` 幂等键。

3. 怎么保证状态不乱？  
   PostgreSQL 状态机只允许合法流转，每次 transition 都写审计日志。

4. 怎么支持人工介入？  
   按规则写入 `review_tasks`，运营后台可以查看待人工任务、队列、原因、金额和动作。

---

### 亮点 3：退款运营后台，让链路效果“看得见”

**做了什么：**

- 新增 `/ops/refunds` 页面；
- 用户可以提交完整退款订单 JSON，或通过 `refund_id` / `order_id` 查询；
- 页面展示：
  - 自动化动作；
  - 处理状态；
  - 金额；
  - 规则命中；
  - 风险等级；
  - 信任分；
  - 人工任务；
  - 全局统计；
  - 原始 JSON；
- 后端复用 `RefundTool` 内的进程级 `AgentService` 和 PostgreSQL 连接池，避免重复创建连接。

**简历写法：**

```text
Built a refund operations console to submit order snapshots and inspect automated actions,
amounts, rule hits, risk tiers, ledger status, audit transitions and manual tasks.
```

**面试价值：**

这解决了个人 Agent 项目常见的“链路跑通但效果不可见”问题。  
你不仅能说“我实现了退款工具”，还能展示一个可操作的验证入口。

---

### 亮点 4：架构重构后具备低耦合和可测试性

**做了什么：**

- 抽取 `app/shared` 公共工具层，统一：
  - JSON 序列化 / 容错解析；
  - SHA-256 / UUIDv4 / UUIDv5；
  - UTC 时间 / 保留期；
  - SSE 帧编码；
  - 文件名清理 / 上传类型校验；
- 抽取 `RAGIndexingPipeline` 端口，让文档索引服务依赖最小接口而不是具体 `RAGPipeline`；
- 统一检索内核 `BM25Index` 和 `rrf_fuse`，避免多路检索和主链路重复实现；
- 架构测试约束：
  - `shared` 不允许依赖 FastAPI / SQLAlchemy / Redis / pymilvus / OpenAI；
  - `domain` 不允许依赖 `api` / `infrastructure`；
  - `core` 不允许依赖 `api`。

**简历写法：**

```text
Refactored the service into a shared utility layer and RAG pipeline port, consolidating BM25/RRF,
JSON, hashing, UUID, SSE and file-validation logic; added architecture tests to prevent reverse
dependencies between domain, core and infrastructure layers.
```

**面试追问可以讲：**

1. 为什么单独抽 `shared`？  
   因为 JSON、哈希、UUID、SSE、文件名校验这些逻辑原本散落在 API、CLI、domain 和 infrastructure 中，容易漂移。

2. 为什么不直接 import 具体实现？  
   索引服务只关心“写向量、删向量、失效 BM25”，不关心完整 Pipeline；用 Protocol 降低耦合，测试也更容易。

3. 怎么防止架构腐化？  
   用 AST 架构守卫测试限制非法 import，而不是只靠口头规范。

---

### 亮点 5：生产化门禁与可观测性

**做了什么：**

- 自动化测试：149 passed；
- PostgreSQL 集成测试：2 passed；
- 覆盖率约 66%；
- Ruff 通过；
- Mypy `--strict` 通过；
- Alembic 管理 public schema；
- Prometheus 指标；
- JSON 结构化日志；
- TraceLog 持久化；
- trace context；
- PostgreSQL / Redis / Milvus 健康矩阵；
- Trace / Message 保留策略；
- Docker Compose 部署。

**简历写法：**

```text
Established production-style quality gates with 149 automated tests, PostgreSQL integration tests,
~66% app coverage, Ruff, mypy --strict, Alembic migrations, Prometheus metrics, structured JSON
logs, TraceLog persistence and PostgreSQL/Redis/Milvus health probes.
```

**面试追问可以讲：**

1. 为什么覆盖率只有 66%？  
   这是实测值，不是编造。核心业务规则和工具链路已有测试，部分 CLI、页面和外部适配层覆盖较低。可以在后续补齐。

2. 为什么用 TraceLog 而不是直接上 OpenTelemetry？  
   当前项目先用 PostgreSQL TraceLog 保证零外部依赖、可查询、可持久化；后续可以替换或扩展为 OTLP。

3. 健康检查为什么分 liveness / readiness？  
   `/health` 判断进程活着；`/health/ready` 判断 PostgreSQL / Redis / Milvus 是否可用，编排系统可以据此摘流量。

---

## 五、难点复盘素材

简历里最有区分度的不是“用了什么”，而是“踩过什么坑、怎么解决”。

### 难点 1：中文 BM25 检索失效

**问题：**  
中文没有天然空格分词，如果整句中文被当成一个 token，BM25 基本无法命中。

**方案：**

- 实现中文 bigram 分词；
- 英文 / 数字仍按词切分；
- 将 BM25 与向量检索结果做 RRF 融合；
- 把 `BM25Index` 和 `rrf_fuse` 抽成共享检索内核。

**简历写法：**

```text
Fixed ineffective Chinese keyword retrieval by implementing bigram-aware BM25 tokenization and
unifying BM25/RRF logic across retrieval paths, improving hybrid recall for policy and order
queries.
```

> 注意：这里没有精确召回提升数字，如果面试官追问，可以说明当前项目尚未做 RAG golden set 前后对比，属于待补测项。

---

### 难点 2：退款不能交给 LLM 生成

**问题：**  
如果退款金额、状态、审批动作由 LLM 决定，会出现不可解释、不可回放和重复退款风险。

**方案：**

- LLM 只负责理解输入；
- 退款意图命中后直接进入工具；
- 风控、金额、状态流转全部由规则和 PostgreSQL 状态机处理；
- 引入幂等台账和审计日志。

**简历写法：**

```text
Moved refund decisions out of LLM generation into a deterministic PostgreSQL-backed workflow with
idempotency keys, state-machine transitions, audit logs and manual-review tasks.
```

---

### 难点 3：多副本知识库同步可能重复写

**问题：**  
多个服务副本同时同步 `knowledge/` 目录时，同一个稳定 `doc_id` 可能被并发处理，导致主键冲突或重复写向量。

**方案：**

- 进程内 `asyncio.Lock` 串行化；
- 增加 PostgreSQL advisory lock；
- 同步前扫描文件 SHA-256，只处理新增 / 更新 / 删除；
- 文档变更后失效 BM25 索引。

**简历写法：**

```text
Prevented concurrent knowledge ingestion conflicts by combining in-process async locks with
PostgreSQL advisory locks and SHA-256-based incremental synchronization.
```

---

### 难点 4：全局时钟导致退款时效规则并发不安全

**问题：**  
早期退款测试时钟使用全局可变状态，并发请求下可能互相覆盖时间。

**方案：**

- 引入 `Clock` Protocol；
- `RefundService` 注入 `SystemClock` 或测试时钟；
- 移除全局 `_FIXED_NOW` 可变状态。

**简历写法：**

```text
Removed mutable global business clock and injected a Clock abstraction into refund services,
making time-based rules deterministic under concurrent requests and easier to test.
```

---

### 难点 5：退款链路跑通但“看不到效果”

**问题：**  
用户只能看到一句话回复，无法知道后台走了哪个规则、状态是否变化、是否退款、是否人工介入。

**方案：**

- 增加退款运营后台 `/ops/refunds`；
- 返回 `AgentResponse` + 内部 `CaseView`；
- 页面展示动作、金额、规则命中、风险等级、人工任务、统计；
- 数据库保留台账和审计流转。

**简历写法：**

```text
Built an operations console to visualize refund decisions, rule hits, workflow transitions,
ledger state and manual tasks, turning the agent workflow into an inspectable and testable
business flow.
```

---

## 六、技术决策清单

| 决策 | 原因 |
|---|---|
| 退款不走 LLM 判定 | 资金动作要求确定性、幂等、审计 |
| 使用 PostgreSQL 退款 schema | 退款需要强一致状态机、台账和事务 |
| 使用 Milvus 做知识库向量检索 | 支持向量索引、集合级隔离和后续扩展 |
| 混合向量 + BM25 + RRF | 中文语义召回和关键词精确召回互补 |
| CrossEncoder 重排 | 最终上下文相关性优于候选召回数量 |
| Redis 缓存 RAG 结果 | 相同请求减少生成成本和延迟 |
| 自研 Tracer + TraceLog | 当前零外部依赖即可定位链路；后续可替换 OTel |
| 模拟 PaymentGateway | 先验证状态机和幂等，再接真实渠道 |
| Alembic 管 public schema | 避免 `create_all` 造成的不可控结构变更 |
| Docker Compose | 一键拉起 PostgreSQL / Redis / Milvus / 应用 |

---

## 七、面试证据链

面试时可以按下面的顺序讲：

1. **场景**  
   “我做一个客服 Agent，既要回答知识库问题，也要处理退款工单。”

2. **关键取舍**  
   “知识问答可以用 LLM + RAG，但退款不能让 LLM 决定。”

3. **架构**  
   “所以我把系统分成 RAG 检索链路、确定性退款链路和运营观测链路。”

4. **量化规模**  
   “22 份资料、1,136 分块、20 条退款规则、13 个工作流状态、149 个测试。”

5. **难点**  
   “中文 BM25 需要重写分词；多副本同步要加 advisory lock；退款时钟要注入；运营后台要能看规则命中和状态流转。”

6. **验证**  
   “当前有 149 个测试，Ruff、Mypy strict、覆盖率、健康检查和 Prometheus 指标。”

7. **边界**  
   “支付网关目前是模拟实现；真实渠道接入、RBAC、压测和 RAG 评测集还在规划中。”

---

## 八、技能栏建议写法

### 大模型与检索增强

```text
熟悉 RAG 工程化落地，实践过 bge-large 向量召回、中文 BM25、RRF 融合、CrossEncoder 重排、
引用生成、Redis 结果缓存与知识库增量同步；了解 Milvus 集合管理与文档分块策略。
```

### Agent 与工具链

```text
熟悉 Agent 工具编排与 ReAct 路由，实践过 Function Calling / Tool Registry / Refund Tool /
Plan-ReAct 分层设计；能把确定性规则、状态机和人工任务接入 Agent 工作流。
```

### 后端与工程化

```text
熟悉 Python、FastAPI、SSE、asyncio、SQLAlchemy 2.0 async、PostgreSQL、Redis、Docker Compose；
实践过熔断、降级、幂等、审计日志、健康检查、Prometheus 指标、结构化日志和 Alembic 迁移。
```

### 质量保障

```text
熟悉 pytest、coverage、Ruff、Mypy strict、API 回归、架构边界测试和 PostgreSQL 集成测试。
```

---

## 九、可以直接写进简历的高分 bullet

以下 bullet 都基于当前项目事实，未编造未测指标。

```text
● Architected a containerized customer-service Agent using FastAPI, DeepSeek, Milvus,
  PostgreSQL, Redis and SSE; ingested 22 documents / 1,136 chunks and exposed 13 OpenAPI
  endpoints for RAG, document ingestion, refunds, health checks and metrics.
```

```text
● Built a hybrid RAG pipeline with bge-large-zh-v1.5, Chinese BM25, RRF fusion and optional
  CrossEncoder reranking; generated citation-grounded answers with Redis caching, knowledge-gap
  fallback and SSE streaming.
```

```text
● Designed a deterministic refund workflow with 20 risk rules, 13 workflow states and 14 test
  scenarios; implemented PostgreSQL state transitions, idempotent ledger entries, audit logs,
  manual-review tasks and a simulated payment gateway port.
```

```text
● Built a refund operations console to submit order snapshots and inspect automated actions,
  amounts, rule hits, risk tier, trust score, ledger state, audit transitions and manual tasks.
```

```text
● Refactored the service into a shared utility layer and RAG pipeline port, consolidating
  BM25/RRF, JSON, hashing, UUID, SSE and file-validation logic while preventing reverse
  dependencies between domain, core and infrastructure layers.
```

```text
● Established quality and observability gates with 149 automated tests, PostgreSQL integration
  tests, ~66% app coverage, Ruff, mypy --strict, Alembic migrations, Prometheus metrics,
  structured JSON logs, TraceLog persistence and dependency health probes.
```

---

## 十、不要写、或暂时不要夸大的内容

为了面试不翻车，以下内容不建议直接写：

| 不要写 | 原因 |
|---|---|
| 支持生产环境万级 QPS | 未压测 |
| 降低 LLM 成本 70% | 没有成本基线 |
| RAG 准确率从 X 提升到 Y | 当前项目尚未建立 golden set 前后对比 |
| 支持真实支付 | 当前是模拟 PaymentGateway |
| 支持多租户 RBAC | 当前有 API Key，但没有完整 RBAC / 租户体系 |
| 支持高可用集群 | 未做多副本压测和故障演练 |
| 企业生产系统 | 更准确的说法是“可容器部署的生产风格原型 / 演示服务” |

---

## 十一、下一步最有性价比的补测项

### 1. 建立 RAG golden set

建议做一个小规模评测集：

```text
问题、期望关键词、期望来源文件、是否允许拒答
```

输出指标：

```text
Recall@K
Hit Rate
MRR
Citation Hit Rate
Refusal Correctness
Faithfulness / Answer Relevancy（可用 RAGAS 或自研评分）
```

有了这组数据，RAG bullet 就能从“实现了混合检索”升级为“可验证检索质量”。

### 2. 压测核心接口

建议测：

```text
GET  /api/v1/health
POST /api/v1/chat              # 命中缓存
POST /api/v1/chat              # 未命中 RAG
POST /api/v1/chat              # 退款工具
POST /api/v1/chat/stream
```

输出：

```text
QPS
P50 / P95 / P99
错误率
缓存命中率
RAG 检索耗时
LLM 首字延迟
退款工具耗时
```

退款链路当前已有 TraceLog duration，可以进一步做并发压测。

### 3. 补真实支付渠道适配

把 `PaymentGateway` 从模拟实现切到 HTTP 网关：

```env
PAYMENT_GATEWAY_MODE=http
PAYMENT_GATEWAY_URL=...
PAYMENT_GATEWAY_TOKEN=...
```

再补对账、补偿、回调和失败演练。

### 4. 增加退款运营 RBAC

当前是 API Key，下一步可以加：

```text
角色：admin / operator / viewer
权限：提交、查询、审批、导出
审计：操作人、时间、动作
```

---

## 十二、投递不同岗位时的侧重调整

### AI 应用开发岗

重点写：

1. RAG 混合检索；
2. Agent 工具编排；
3. 引用生成与拒答；
4. 退款工具；
5. Redis 缓存与降级；
6. 149 个测试。

### Python 后端岗

重点写：

1. FastAPI + SSE + asyncio；
2. SQLAlchemy async + PostgreSQL 状态机；
3. 幂等台账和审计；
4. Redis；
5. Alembic；
6. 健康检查与指标。

### Agent / LLM 工程岗

重点写：

1. 意图路由；
2. Tool Registry；
3. ReAct；
4. RAG；
5. LLM 降级；
6. 确定性退款工作流；
7. TraceLog 与运营后台。

### 全栈 / AI 产品方向

重点写：

1. `/ui` 聊天演示；
2. `/ops/refunds` 运营后台；
3. `/docs` 离线 API 文档；
4. 退款结果可视化；
5. 数据库台账与人工任务。

---

## 十三、最终简历推荐版本

如果要控制篇幅，推荐用下面这个版本。

```text
Enterprise AI Agent · 可引用 RAG 与确定性退款工作流
技术栈：Python / FastAPI + SSE / asyncio / DeepSeek / Milvus + bge-large-zh-v1.5 /
       PostgreSQL + SQLAlchemy 2.0 async / Redis / Alembic / Prometheus / pytest

项目介绍：
面向客服场景的可容器部署 Agent 服务，融合知识库问答、确定性退款工作流与运营后台。
系统将 22 份资料 / 1,136 分块接入 Milvus，支持带 [n] 引用的混合检索问答；退款动作不交给
LLM，而由 20 条规则、13 个状态机、幂等台账、审计日志和人工任务驱动。

个人工作：
● Built hybrid RAG：bge-large 向量召回 + 中文 BM25 + RRF + CrossEncoder 重排，结合 Redis
  缓存、引用生成、SSE 流式输出与 RAG/LLM 异常降级。
● Designed deterministic refunds：20 条风控规则、14 类场景、幂等台账、模拟支付网关适配、
  PostgreSQL 状态机与审计日志，避免 LLM 直接决定资金动作。
● Built ops console：/ops/refunds 提交订单快照后实时查看动作、金额、规则命中、风险等级、
  台账状态、人工任务和全局统计。
● Refactored architecture：抽取 shared 纯函数层和 RAG Pipeline 端口，统一 BM25/RRF、JSON、
  哈希、UUID、SSE 与文件校验，并用架构测试防止层间反向依赖。
● Established quality gates：149 tests / 2 integration tests / ~66% coverage / Ruff /
  Mypy strict / Alembic / Prometheus / JSON logs / TraceLog / health probes。
```

---

## 十四、一句话总结

这个项目的简历主线不是“我调用了 DeepSeek”，而是：

> **我把一个容易变成 Prompt Demo 的客服 Agent，拆成了可引用 RAG、可审计退款工作流、可运营验证后台和可观测服务，并用 149 个测试和 strict 类型门禁保证它能持续演进。**
