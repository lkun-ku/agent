-- 退款工作流：独立 refund schema；生产由 PostgreSQL 迁移执行。
-- 开发环境 PostgresRefundStore 也会幂等 ensure_schema。

CREATE SCHEMA IF NOT EXISTS refund;
SET search_path TO refund, public;
CREATE TABLE IF NOT EXISTS users(
  user_id TEXT PRIMARY KEY,
  risk_level TEXT,
  refund_rate_30d NUMERIC(8,4),
  credit_score INTEGER DEFAULT 80
);
CREATE TABLE IF NOT EXISTS orders(
  order_id TEXT PRIMARY KEY,
  user_id TEXT,
  paid_amount NUMERIC(12,2),
  refundable_amount NUMERIC(12,2),
  order_status TEXT,
  delivered_at TEXT,
  goods_amount NUMERIC(12,2),
  freight_amount NUMERIC(12,2),
  tax_amount NUMERIC(12,2),
  discount_amount NUMERIC(12,2)
);
CREATE TABLE IF NOT EXISTS refund_requests(
  refund_id TEXT PRIMARY KEY,
  order_id TEXT,
  user_id TEXT,
  idempotency_key TEXT,
  return_id TEXT,
  action_code TEXT,
  status_code TEXT,
  raw_json TEXT,
  refundable_cents BIGINT,
  requested_cents BIGINT,
  scenario TEXT,
  expected_action TEXT,
  reason_code TEXT,
  reason_name TEXT
);
CREATE TABLE IF NOT EXISTS return_orders(
  return_id TEXT PRIMARY KEY,
  refund_id TEXT,
  order_id TEXT,
  user_id TEXT,
  session_id TEXT,
  status TEXT,
  workflow_status TEXT,
  reason TEXT,
  reason_code TEXT,
  plan TEXT,
  requested_amount NUMERIC(12,2),
  approved_amount NUMERIC(12,2),
  refunded_amount NUMERIC(12,2) DEFAULT 0,
  action_code TEXT,
  queue TEXT,
  trust_score INTEGER,
  risk_tier TEXT,
  risk_json TEXT,
  evidence_json TEXT,
  reply TEXT,
  handoff_json TEXT,
  return_required INTEGER,
  return_status TEXT
);
CREATE TABLE IF NOT EXISTS refund_ledger(
  idem_key TEXT PRIMARY KEY,
  return_id TEXT,
  amount NUMERIC(12,2),
  status TEXT
);
CREATE TABLE IF NOT EXISTS review_tasks(
  return_id TEXT,
  queue TEXT,
  payload_json TEXT,
  decision_json TEXT,
  status TEXT,
  reviewer TEXT,
  note TEXT,
  id BIGSERIAL PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS audit_log(
  id BIGSERIAL PRIMARY KEY,
  return_id TEXT,
  actor TEXT,
  action TEXT,
  detail_json TEXT
);
CREATE TABLE IF NOT EXISTS kv(
  k TEXT PRIMARY KEY,
  v TEXT
);
CREATE INDEX IF NOT EXISTS idx_refund_requests_order ON refund_requests(order_id);
CREATE INDEX IF NOT EXISTS idx_refund_requests_idem ON refund_requests(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_return_orders_status ON return_orders(status);
