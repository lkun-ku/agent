"""共享纯函数工具集。

该包只承载与业务状态无关的通用能力，禁止引入 FastAPI、SQLAlchemy、
Milvus、Redis 等基础设施依赖，保证工具单元可被任何层复用。
"""
