"""应用配置：基于 pydantic-settings，支持环境变量与 .env 文件。"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="enterprise-ai-agent", description="服务名称")
    app_env: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=False, description="调试模式")
    api_prefix: str = Field(default="/api/v1", description="API 前缀")
    host: str = Field(
        default="127.0.0.1",
        description="监听地址；容器内或需局域网访问时设为 0.0.0.0",
    )
    port: int = Field(default=8000, description="监听端口")

    # ---- LLM：DeepSeek（OpenAI 兼容协议）----
    openai_api_key: str = Field(default="", description="DeepSeek API Key")
    openai_api_base: str = Field(
        default="https://api.deepseek.com",
        description="DeepSeek OpenAI 兼容 Base（官方地址，无需 /v1 后缀）",
    )
    openai_model: str = Field(
        default="deepseek-flash",
        description="默认对话模型（DeepSeek-V4.1-Flash）",
    )
    openai_thinking: bool = Field(
        default=False,
        description="是否启用思考模式；开启后 temperature 不生效且延迟/费用更高",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/agent_db",
        description="SQLAlchemy 异步数据库 URL（推荐 postgresql+asyncpg）",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL")

    milvus_host: str = Field(default="localhost", description="Milvus 主机")
    milvus_port: int = Field(default=19530, description="Milvus 端口")
    milvus_user: str = Field(default="", description="Milvus 用户名")
    milvus_password: str = Field(default="", description="Milvus 密码")
    milvus_collection_name: str = Field(
        default="agent_knowledge",
        description="默认向量集合名",
    )

    # ---- RAG（检索增强）----
    rag_enabled: bool = Field(default=True, description="对话时是否启用知识库检索增强")
    rag_top_k: int = Field(default=4, ge=1, le=20, description="检索返回的分块条数")
    rag_max_distance: float = Field(
        default=1.1,
        gt=0,
        description="向量距离阈值（L2，越小越相似）；超过则视为未命中并回退普通对话",
    )
    rag_collection_name: str = Field(
        default="knowledge_chunks",
        description="文档分块向量集合名",
    )
    embedding_model: str = Field(
        default="BAAI/bge-small-zh-v1.5",
        description="嵌入模型名或本地路径（中文小模型，512 维）",
    )
    embedding_local_only: bool = Field(
        default=True,
        description="仅加载本地缓存的嵌入模型；无网络环境请保持 true",
    )

    reranker_model: str = Field(
        default="",
        description="重排模型名或本地路径；留空表示不启用重排",
    )
    rag_rerank_candidates: int = Field(
        default=12,
        ge=1,
        le=50,
        description="启用重排时先召回的候选分块数",
    )

    knowledge_dir: str = Field(
        default="knowledge",
        description="知识库源文档目录：放入文件后同步/自动扫描入库",
    )
    knowledge_autoscan: bool = Field(
        default=True,
        description="服务启动时自动扫描知识库目录并增量入库",
    )

    upload_dir: str = Field(default="uploads", description="文档本地存储目录")
    max_upload_mb: int = Field(default=20, description="单文件上传体积上限（MB）")

    # ---- API 鉴权 ----
    api_auth_enabled: bool = Field(
        default=False,
        description="是否要求 X-API-Key；生产环境必须为 true",
    )
    api_key: str | None = Field(default=None, description="内部 API Key；不入库不入镜像")

    # ---- 支付网关 ----
    payment_gateway_mode: str = Field(
        default="simulated",
        description="simulated / http；生产必须使用真实网关",
    )
    payment_gateway_url: str | None = Field(
        default=None,
        description="HTTP 网关退款接口 URL",
    )
    payment_gateway_token: str | None = Field(
        default=None,
        description="HTTP 网关 Token",
    )
    payment_gateway_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="HTTP 网关超时秒数",
    )

    # ---- 会话与追踪持久化 ----
    conversation_persistence_enabled: bool = Field(
        default=True,
        description="是否将 /chat 的用户输入与最终回复写入 Conversation/Message",
    )
    trace_persistence_enabled: bool = Field(
        default=True,
        description="是否将内存 Tracer 的 Span 写入 TraceLog",
    )

    # ---- RAG 缓存与混合检索 ----
    rag_cache_enabled: bool = Field(
        default=True,
        description="是否缓存 RAG 命中结果；退款工具永不走缓存",
    )
    rag_cache_ttl_seconds: int = Field(
        default=3600,
        ge=1,
        le=86400 * 7,
        description="RAG 缓存 TTL",
    )
    rag_retrieval_mode: str = Field(
        default="hybrid",
        description="检索模式：vector / keyword / hybrid",
    )

    # ---- 通用 Agent Orchestrator ----
    agent_orchestrator_enabled: bool = Field(
        default=True,
        description="是否对任务类意图启用 ReAct/Plan-Execute 编排",
    )
    agent_max_steps: int = Field(
        default=8,
        ge=1,
        le=20,
        description="ReAct 最大步数",
    )

    # ---- 意图识别：强规则优先，语义近邻兜底 ----
    intent_semantic_enabled: bool = Field(
        default=True,
        description="规则置信度不足时是否启用本地嵌入语义分类兜底",
    )
    intent_semantic_min_similarity: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="语义分类采用的最低余弦相似度",
    )

    # ---- 依赖超时与连接池 ----
    redis_socket_timeout: float = Field(default=5.0, ge=1.0, le=60.0)
    redis_socket_connect_timeout: float = Field(default=5.0, ge=1.0, le=60.0)
    redis_health_check_interval: int = Field(default=30, ge=5, le=300)
    database_connect_timeout: float = Field(default=5.0, ge=1.0, le=60.0)
    database_command_timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    milvus_timeout: float = Field(default=10.0, ge=1.0, le=120.0)

    # ---- LLM 重试（只影响瞬时网络错误；熔断器仍负责跨请求保护）----
    llm_max_retries: int = Field(default=1, ge=0, le=3, description="单模型最大重试次数")
    llm_retry_base_delay: float = Field(
        default=0.5, ge=0.0, le=10.0, description="指数退避基础秒数"
    )
    llm_retry_max_delay: float = Field(
        default=5.0, ge=0.0, le=60.0, description="单次重试最大等待秒数"
    )

    # ---- 退款 Agent 工具（默认关闭，不单独开服务）----
    refund_enabled: bool = Field(default=False, description="是否注册 refund Agent 工具")
    refund_data_dir: str = Field(
        default="data/refund",
        description="退款工具的数据集目录（仅演示/回归时使用）",
    )
    refund_seed_dataset: bool = Field(
        default=False,
        description="是否把数据集 seed 进退款库；生产保持 false",
    )

    log_level: str = Field(default="INFO", description="日志级别")
    log_json: bool = Field(default=False, description="是否输出 JSON 结构化日志")
    trace_log_retention_days: int = Field(
        default=30,
        ge=1,
        le=3650,
        description="TraceLog 保留天数",
    )
    conversation_log_retention_days: int = Field(
        default=90,
        ge=1,
        le=3650,
        description="Conversation/Message 保留天数",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
