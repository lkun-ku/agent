"""安全基础设施。"""

from app.infrastructure.security.auth import require_api_key

__all__ = ["require_api_key"]
