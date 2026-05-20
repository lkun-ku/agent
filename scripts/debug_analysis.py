"""直连 AnalysisService 调试：打印每一步与 trace，便于定位未收敛问题。"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.chat import get_model_router  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.infrastructure.database import session as db_session  # noqa: E402
from app.infrastructure.trace.tracer import Tracer  # noqa: E402
from app.services.analysis_service import AnalysisService  # noqa: E402


async def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else "华东区已支付订单的销售额是多少？"
    settings = get_settings()
    engine = db_session.init_engine(settings.database_url)
    db_session.configure_session(engine)

    tracer = Tracer()
    service = AnalysisService(
        get_model_router(),
        db_session.async_session_factory,
        tracer,
    )
    response = await service.run(question, "debug-analysis")

    print("success", response.success)
    print("error", response.error)
    print("answer", response.answer)
    for index, step in enumerate(response.steps):
        print(f"STEP {index}: {json.dumps(step, ensure_ascii=False, default=str)[:500]}")
    record = tracer.get_trace(response.trace_id)
    if record:
        for span in record.spans:
            print("SPAN", span.operation, "error=", span.error, "result=", span.result)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
