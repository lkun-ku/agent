"""生成经营分析 demo 数据（demo_customers / demo_products / demo_orders）。

用法：
    $env:DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/agent_db"
    .\\.venv\\Scripts\\python.exe scripts\\seed_demo_db.py
    .\\.venv\\Scripts\\python.exe scripts\\seed_demo_db.py --reset
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
from datetime import datetime, timedelta

from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    Numeric,
    String,
    Table,
    delete,
    func,
    select,
)
from sqlalchemy.ext.asyncio import create_async_engine

REGIONS = ["华东", "华南", "华北", "西南"]
SEGMENTS = ["企业", "中小", "个人"]
CATEGORIES = ["电子", "办公", "家居", "耗材"]
STATUSES = ["paid"] * 85 + ["refunded"] * 10 + ["cancelled"] * 5
BASE_DAY = datetime(2026, 5, 7)

metadata = MetaData()
customers = Table(
    "demo_customers",
    metadata,
    Column("id", String(16), primary_key=True),
    Column("name", String(64), nullable=False),
    Column("region", String(16), nullable=False),
    Column("segment", String(16), nullable=False),
    Column("created_at", DateTime, nullable=False),
)
products = Table(
    "demo_products",
    metadata,
    Column("id", String(16), primary_key=True),
    Column("name", String(64), nullable=False),
    Column("category", String(16), nullable=False),
    Column("price", Numeric(10, 2), nullable=False),
    Column("cost", Numeric(10, 2), nullable=False),
)
orders = Table(
    "demo_orders",
    metadata,
    Column("id", String(16), primary_key=True),
    Column("customer_id", String(16), nullable=False),
    Column("product_id", String(16), nullable=False),
    Column("quantity", Numeric(10, 0), nullable=False),
    Column("amount", Numeric(12, 2), nullable=False),
    Column("status", String(16), nullable=False),
    Column("created_at", DateTime, nullable=False),
)


def build_rows(seed: int = 42) -> tuple[list[dict], list[dict], list[dict]]:
    rnd = random.Random(seed)
    customer_rows: list[dict] = []
    for i in range(1, 121):
        customer_rows.append(
            {
                "id": f"C{i:04d}",
                "name": f"客户{i:03d}",
                "region": rnd.choice(REGIONS),
                "segment": rnd.choice(SEGMENTS),
                "created_at": BASE_DAY - timedelta(days=rnd.randint(0, 540)),
            }
        )

    product_rows: list[dict] = []
    for i in range(1, 41):
        price = round(rnd.uniform(20, 2000), 2)
        product_rows.append(
            {
                "id": f"P{i:04d}",
                "name": f"商品{i:03d}",
                "category": rnd.choice(CATEGORIES),
                "price": price,
                "cost": round(price * rnd.uniform(0.5, 0.8), 2),
            }
        )

    order_rows: list[dict] = []
    for i in range(1, 801):
        customer = rnd.choice(customer_rows)
        product = rnd.choice(product_rows)
        quantity = rnd.randint(1, 5)
        order_rows.append(
            {
                "id": f"O{i:05d}",
                "customer_id": customer["id"],
                "product_id": product["id"],
                "quantity": quantity,
                "amount": round(float(product["price"]) * quantity, 2),
                "status": rnd.choice(STATUSES),
                "created_at": BASE_DAY - timedelta(days=rnd.randint(0, 365)),
            }
        )
    return customer_rows, product_rows, order_rows


async def main_async(reset: bool) -> None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("请设置 DATABASE_URL（asyncpg）")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(url)
    customer_rows, product_rows, order_rows = build_rows()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
            existing = await conn.scalar(select(func.count()).select_from(orders))
            if existing and not reset:
                print(f"demo 数据已存在（orders={existing}），跳过；需要重建加 --reset")
                return
            if reset:
                await conn.execute(delete(orders))
                await conn.execute(delete(products))
                await conn.execute(delete(customers))
            await conn.execute(customers.insert(), customer_rows)
            await conn.execute(products.insert(), product_rows)
            await conn.execute(orders.insert(), order_rows)
        print(
            f"seeded customers={len(customer_rows)} "
            f"products={len(product_rows)} orders={len(order_rows)}"
        )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    asyncio.run(main_async(args.reset))


if __name__ == "__main__":
    main()
