# Shared 工具集

`app/shared` 只允许承载纯函数、常量和轻量类型，不允许依赖 FastAPI、SQLAlchemy、Redis、Milvus、OpenAI 等基础设施包。

## 模块清单

| 模块 | 能力 | 使用场景 |
|---|---|---|
| `jsonx` | JSON 序列化、空值容错反序列化 | 缓存、数据库 JSON 字段、日志 payload |
| `hashing` | SHA-256、UUIDv4、UUIDv5 | 文件指纹、缓存 key、Trace/Span/文档 ID |
| `times` | UTC 当前时间、保留期截止点、秒级诊断时间 | 数据库保留清理、诊断页 |
| `files` | 文件名清理、上传类型白名单 | 文档上传与 CLI 校验 |
| `http` | SSE 数据帧编码 | `/chat/stream` |

## 约定

1. 新增通用函数前，先确认至少有两个调用方。
2. 工具函数必须完整类型标注、中文使用注释，并有单元测试。
3. 不在这里放业务状态、数据库连接、全局配置或 HTTP 客户端。
4. 不引入隐式配置读取；需要配置时由调用方传入。
