"""根路径页面：服务总览与内置聊天演示页。

仅用于本地快速验证效果，不参与 OpenAPI 文档（``include_in_schema=False``）。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["web"], include_in_schema=False)

# 页面禁用缓存：避免浏览器继续使用旧版页面（如依赖 CDN 的 Swagger）
_NO_STORE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-Content-Type-Options": "nosniff",
}

_BASE_STYLE = """
*{box-sizing:border-box}
body{margin:0;background:#0d1117;color:#e6edf3;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;
  line-height:1.6}
a{color:#58a6ff;text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:880px;margin:0 auto;padding:40px 24px 64px}
h1{font-size:26px;margin:0 0 6px}
.sub{color:#8b949e;margin:0 0 28px;font-size:14px}
.card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:18px 20px;margin-bottom:16px}
.card h2{font-size:15px;margin:0 0 10px;color:#e6edf3;font-weight:600}
.muted{color:#8b949e;font-size:13px}
code{background:#0d1117;border:1px solid #30363d;border-radius:5px;
  padding:1px 6px;font-size:12.5px;font-family:ui-monospace,Consolas,monospace}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #21262d;vertical-align:top}
th{color:#8b949e;font-weight:500}
.badge{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;
  border:1px solid #30363d;border-radius:999px;padding:3px 10px;color:#8b949e}
.dot{width:7px;height:7px;border-radius:50%;background:#8b949e}
.dot.ok{background:#3fb950}
.dot.bad{background:#f85149}
.links{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.link{display:block;background:#0d1117;border:1px solid #30363d;border-radius:10px;
  padding:12px 14px}
.link b{display:block;font-size:14px;margin-bottom:2px}
.link span{color:#8b949e;font-size:12.5px}
"""

_INDEX_HTML = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>企业级 AI Agent 服务</title>
<style>{_BASE_STYLE}</style>
</head>
<body>
<div class="wrap">
  <h1>企业级 AI Agent 服务</h1>
  <p class="sub">FastAPI + DeepSeek（OpenAI 兼容协议）· 服务已启动</p>

  <div class="card">
    <h2>运行状态</h2>
    <span class="badge"><span class="dot" id="dot"></span><span id="status">检测中…</span></span>
    <p class="muted" id="env"></p>
  </div>

  <div class="card">
    <h2>快速入口</h2>
    <div class="links">
      <a class="link" href="/ui"><b>聊天演示页</b><span>浏览器里直接对话，验证模型连通</span></a>
      <a class="link" href="/docs"><b>Swagger UI</b><span>交互式 API 文档与调试</span></a>
      <a class="link" href="/redoc"><b>ReDoc</b><span>只读接口文档</span></a>
      <a class="link" href="/api/v1/health"><b>健康检查</b><span>GET /api/v1/health</span></a>
    </div>
  </div>

  <div class="card">
    <h2>接口一览</h2>
    <table>
      <tr><th>方法</th><th>路径</th><th>说明</th></tr>
      <tr><td>GET</td><td><code>/api/v1/health</code></td><td>存活探针，不依赖中间件</td></tr>
      <tr><td>GET</td><td><code>/api/v1/health/ready</code></td><td>就绪探针，检查 PostgreSQL（不可用返回 503）</td></tr>
      <tr><td>POST</td><td><code>/api/v1/chat</code></td><td>非流式对话（意图识别 + 模型路由 + 熔断）</td></tr>
      <tr><td>POST</td><td><code>/api/v1/chat/stream</code></td><td>SSE 流式对话</td></tr>
      <tr><td>POST</td><td><code>/api/v1/documents/upload</code></td><td>上传 TXT/PDF，ETL 分块后入库（需 PostgreSQL）</td></tr>
      <tr><td>GET</td><td><code>/api/v1/documents</code></td><td>文档列表（需 PostgreSQL）</td></tr>
    </table>
  </div>

  <p class="muted">提示：浏览器请访问 <code>http://127.0.0.1:8000</code>，<code>0.0.0.0</code> 只是监听地址，不能直接打开。</p>
</div>
<script>
fetch('/api/v1/health').then(r => r.json()).then(d => {{
  document.getElementById('status').textContent = '服务正常 · ' + d.status;
  document.getElementById('dot').className = 'dot ok';
}}).catch(() => {{
  document.getElementById('status').textContent = '服务不可用';
  document.getElementById('dot').className = 'dot bad';
}});
fetch('/api/v1/health/ready').then(async r => {{
  const d = await r.json();
  document.getElementById('env').textContent =
    '环境：' + d.app_env + ' · 数据库：' + (d.database === 'up' ? '已连接' : '未连接');
}}).catch(() => {{}});
</script>
</body>
</html>
"""

_CHAT_HTML = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>聊天演示 · 企业级 AI Agent</title>
<style>{_BASE_STYLE}
.wrap{{max-width:820px;padding-bottom:24px}}
.toolbar{{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}}
.panel{{background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden}}
.msgs{{padding:18px;height:min(56vh,460px);overflow-y:auto;display:flex;flex-direction:column;gap:12px}}
.msg{{max-width:86%;padding:10px 14px;border-radius:12px;font-size:14px;white-space:pre-wrap;
  word-break:break-word}}
.msg.user{{align-self:flex-end;background:#1f6feb;color:#fff;border-bottom-right-radius:4px}}
.msg.assistant{{align-self:flex-start;background:#21262d;border-bottom-left-radius:4px}}
.msg.system{{align-self:center;background:transparent;color:#8b949e;font-size:12.5px}}
.composer{{display:flex;gap:10px;padding:12px;border-top:1px solid #30363d;background:#0d1117}}
textarea{{flex:1;resize:none;height:64px;background:#161b22;color:#e6edf3;
  border:1px solid #30363d;border-radius:10px;padding:10px 12px;font:inherit;font-size:14px}}
textarea:focus{{outline:none;border-color:#1f6feb}}
button{{background:#238636;color:#fff;border:0;border-radius:10px;padding:0 20px;
  font-size:14px;cursor:pointer}}
button:disabled{{opacity:.55;cursor:not-allowed}}
.meta{{color:#8b949e;font-size:12px;padding:0 12px 10px}}
label{{font-size:12.5px;color:#8b949e;display:flex;align-items:center;gap:6px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="toolbar">
    <div>
      <h1>聊天演示</h1>
      <p class="sub" style="margin:0">调用 POST /api/v1/chat，真实走 DeepSeek</p>
    </div>
    <a href="/">返回总览</a>
  </div>

  <div class="panel">
    <div class="msgs" id="msgs">
      <div class="msg system">输入内容后回车发送，Shift + 回车换行</div>
    </div>
    <div class="composer">
      <textarea id="input" placeholder="例如：用一句话解释什么是 RAG"></textarea>
      <button id="send">发送</button>
    </div>
    <div class="meta" id="meta"></div>
  </div>

  <p class="muted" style="margin-top:14px">
    流式输出使用 <code>/api/v1/chat/stream</code>
    <label style="display:inline-flex;margin-left:12px">
      <input type="checkbox" id="stream"> 启用流式
    </label>
  </p>
</div>
<script>
const msgsEl = document.getElementById('msgs');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('send');
const metaEl = document.getElementById('meta');
const streamEl = document.getElementById('stream');
const history = [];

function addMsg(role, text) {{
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.textContent = text;
  msgsEl.appendChild(div);
  msgsEl.scrollTop = msgsEl.scrollHeight;
  return div;
}}

async function send() {{
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = '';
  addMsg('user', text);
  history.push({{ role: 'user', content: text }});
  sendBtn.disabled = true;
  metaEl.textContent = '请求中…';

  try {{
    if (streamEl.checked) {{
      await sendStream(text);
    }} else {{
      await sendSync(text);
    }}
  }} catch (err) {{
    addMsg('system', '请求失败：' + err.message);
    metaEl.textContent = '';
  }} finally {{
    sendBtn.disabled = false;
    inputEl.focus();
  }}
}}

async function sendSync(text) {{
  const res = await fetch('/api/v1/chat', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ messages: history, temperature: 0.7 }})
  }});
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || ('HTTP ' + res.status));
  addMsg('assistant', data.content || '(空回复)');
  history.push({{ role: 'assistant', content: data.content }});
  const usage = data.usage || {{}};
  metaEl.textContent = '模型 ' + data.model + ' · tokens ' +
    (usage.total_tokens ?? '-') + ' · trace ' + (data.trace_id || '-').slice(0, 8);
  renderCitations(data.citations);
}}

function renderCitations(list) {{
  if (!list || !list.length) return;
  const text = list.map(function (c) {{
    return '[' + c.index + '] ' + (c.snippet || '').slice(0, 60);
  }}).join('\\n');
  addMsg('system', '引用来源：\\n' + text);
}}

async function sendStream(text) {{
  const res = await fetch('/api/v1/chat/stream', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ messages: history, temperature: 0.7 }})
  }});
  if (!res.ok || !res.body) throw new Error('HTTP ' + res.status);

  const bubble = addMsg('assistant', '');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let answer = '';
  let traceId = '';

  while (true) {{
    const {{ value, done }} = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, {{ stream: true }});
    const parts = buffer.split('\\n\\n');
    buffer = parts.pop() || '';
    for (const part of parts) {{
      const line = part.trim();
      if (!line.startsWith('data:')) continue;
      const payload = JSON.parse(line.slice(5).trim());
      if (payload.error) throw new Error(payload.error);
      if (payload.content) {{
        answer += payload.content;
        bubble.textContent = answer;
        msgsEl.scrollTop = msgsEl.scrollHeight;
      }}
      if (payload.trace_id) traceId = payload.trace_id;
      if (payload.citations) renderCitations(payload.citations);
    }}
  }}

  history.push({{ role: 'assistant', content: answer }});
  metaEl.textContent = '流式输出 · trace ' + (traceId || '-').slice(0, 8);
}}

sendBtn.addEventListener('click', send);
inputEl.addEventListener('keydown', (e) => {{
  if (e.key === 'Enter' && !e.shiftKey) {{
    e.preventDefault();
    send();
  }}
}});
inputEl.focus();
</script>
</body>
</html>
"""


_DOCS_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>API 文档 · 企业级 AI Agent</title>
<style>__BASE_STYLE__
.layout{display:grid;grid-template-columns:320px 1fr;gap:16px;align-items:start}
@media(max-width:820px){.layout{grid-template-columns:1fr}}
.ep{display:flex;gap:8px;align-items:baseline;padding:7px 8px;border-radius:7px;cursor:pointer;
  font-size:13px;border:1px solid transparent}
.ep:hover{background:#0d1117;border-color:#30363d}
.ep.active{background:#0d1117;border-color:#1f6feb}
.ep .p{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;word-break:break-all}
.m{font-size:10.5px;font-weight:700;letter-spacing:.4px;padding:1px 6px;border-radius:4px;color:#fff}
.m.get{background:#1f6feb}.m.post{background:#238636}.m.put{background:#9e6a03}.m.delete{background:#da3633}
.tag{font-size:11.5px;color:#8b949e;margin:14px 0 4px;text-transform:uppercase;letter-spacing:.6px}
.row{display:flex;gap:8px;margin:8px 0}
.row label{min-width:88px;font-size:12.5px;color:#8b949e;padding-top:6px}
.row input,.row textarea{flex:1;background:#0d1117;color:#e6edf3;border:1px solid #30363d;
  border-radius:8px;padding:7px 10px;font:inherit;font-size:13px}
.row textarea{min-height:130px;font-family:ui-monospace,Consolas,monospace;font-size:12.5px}
pre{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:12px;overflow:auto;
  font-size:12.5px;max-height:340px}
.hint{font-size:12.5px;color:#8b949e;margin:4px 0 12px}
</style>
</head>
<body>
<div class="wrap" style="max-width:1080px">
  <h1>API 文档</h1>
  <p class="sub">由 <code>/openapi.json</code> 本地渲染，不依赖任何 CDN，可直接在线调试</p>
  <div class="layout">
    <div class="card" id="list">__SERVER_LIST__</div>
    <div class="card" id="detail"><span class="muted">从左侧选择一个接口</span></div>
  </div>
</div>
<script>
const listEl = document.getElementById('list');
const detailEl = document.getElementById('detail');
let spec = null;
let current = null;

function esc(v) {
  return String(v == null ? '' : v).replace(/[&<>"]/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]
  ));
}
function resolveRef(node) {
  if (!node || !node.$ref) return node;
  let cur = spec;
  for (const part of node.$ref.replace('#/','').split('/')) cur = cur[part];
  return cur;
}
function sample(schema, depth) {
  depth = depth || 0;
  if (!schema || depth > 6) return null;
  schema = resolveRef(schema);
  if (schema.allOf) return Object.assign({}, ...schema.allOf.map(s => sample(s, depth+1)));
  const t = schema.type;
  if (t === 'object' || schema.properties) {
    const out = {};
    for (const [k, v] of Object.entries(schema.properties || {})) out[k] = sample(v, depth+1);
    return out;
  }
  if (t === 'array') return [sample(schema.items || {}, depth+1)];
  if (t === 'integer' || t === 'number') return schema.default != null ? schema.default : 0;
  if (t === 'boolean') return schema.default != null ? schema.default : false;
  if (schema.enum) return schema.enum[0];
  return schema.default != null ? schema.default : '';
}

// 接口列表由服务端渲染，即使 JS 失效也能看到全部接口；
// JS 只负责绑定调试交互，失败时不影响文档阅读。
fetch('/openapi.json').then(r => r.json()).then(s => { spec = s; bindRows(); })
  .catch(() => {});

function bindRows() {
  document.querySelectorAll('.ep').forEach(row => {
    row.onclick = () => {
      document.querySelectorAll('.ep').forEach(e => e.classList.remove('active'));
      row.classList.add('active');
      const path = row.dataset.path;
      const method = row.dataset.method;
      showDetail({ path, method, op: spec.paths[path][method] });
    };
  });
}

function showDetail(ep) {
  current = ep;
  const op = ep.op;
  const params = (op.parameters || []).filter(p => p.in === 'path' || p.in === 'query');
  const bodySchema = op.requestBody && op.requestBody.content
    && (op.requestBody.content['application/json'] || {}).schema;
  let html = '<h2>' + esc(op.summary || ep.path) + '</h2>'
    + '<p class="hint"><span class="m ' + ep.method + '">' + ep.method.toUpperCase() + '</span> '
    + '<code>' + esc(ep.path) + '</code></p>';
  for (const p of params) {
    html += '<div class="row"><label>' + esc(p.name) + (p.required ? ' *' : '') + '</label>'
      + '<input id="param-' + esc(p.name) + '" placeholder="' + esc(p.in) + ' 参数" value=""></div>';
  }
  if (bodySchema) {
    html += '<div class="row"><label>请求体</label><textarea id="body">'
      + esc(JSON.stringify(sample(bodySchema), null, 2)) + '</textarea></div>';
  }
  html += '<div class="row"><label></label><button id="send" style="padding:8px 18px">发送请求</button></div>'
    + '<pre id="resp" style="display:none"></pre>';
  detailEl.innerHTML = html;

  const btn = document.getElementById('send');
  btn.onclick = send;
}

async function send() {
  const op = current.op;
  let path = current.path;
  for (const p of (op.parameters || [])) {
    if (p.in !== 'path') continue;
    const el = document.getElementById('param-' + p.name);
    path = path.replace('{' + p.name + '}', encodeURIComponent(el ? el.value : ''));
  }
  const query = new URLSearchParams();
  for (const p of (op.parameters || [])) {
    if (p.in !== 'query') continue;
    const el = document.getElementById('param-' + p.name);
    if (el && el.value) query.set(p.name, el.value);
  }
  const url = path + (query.toString() ? '?' + query.toString() : '');
  const opts = { method: current.method.toUpperCase(), headers: {} };
  const bodyEl = document.getElementById('body');
  if (bodyEl && bodyEl.value.trim()) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = bodyEl.value;
  }
  const respEl = document.getElementById('resp');
  respEl.style.display = 'block';
  respEl.textContent = '请求中…';
  try {
    const r = await fetch(url, opts);
    const text = await r.text();
    let pretty = text;
    try { pretty = JSON.stringify(JSON.parse(text), null, 2); } catch (e) {}
    respEl.textContent = 'HTTP ' + r.status + '\\n\\n' + pretty;
  } catch (err) {
    respEl.textContent = '请求失败：' + err.message;
  }
}
</script>
</body>
</html>
"""

_DOCS_HTML = _DOCS_TEMPLATE.replace("__BASE_STYLE__", _BASE_STYLE)

_DIAG_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>连通性诊断 · 企业级 AI Agent</title>
<style>__BASE_STYLE__
pre{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:12px;overflow:auto;font-size:12.5px}
li{margin:4px 0;font-size:13px}
</style>
</head>
<body>
<div class="wrap" style="max-width:760px">
  <h1>连通性诊断</h1>
  <p class="sub">用于定位「首次打不开 / 页面空白」是服务端、代理还是缓存问题</p>

  <div class="card">
    <h2>服务端看到的请求</h2>
    <pre id="info">__INFO__</pre>
  </div>

  <div class="card">
    <h2>浏览器端探测</h2>
    <ul id="probe"><li>正在检测…</li></ul>
  </div>

  <div class="card">
    <h2>常见原因与处理</h2>
    <p class="muted">
      1) 首次打不开、返回后再进就行 —— 通常是系统代理 / VPN 拦截了 127.0.0.1：
      在浏览器「代理例外」中加入 <code>127.0.0.1</code> 与 <code>localhost</code>，或临时关闭代理。<br>
      2) 页面空白且像是旧版 Swagger —— 浏览器缓存了旧页面，按 <code>Ctrl+Shift+R</code> 强刷；
      服务端已对所有页面下发 <code>Cache-Control: no-store</code>。<br>
      3) 用地址 <code>http://127.0.0.1:8000</code>，不要用 <code>0.0.0.0</code>。
    </p>
  </div>
</div>
<script>
const probeEl = document.getElementById('probe');
probeEl.innerHTML = '';

function add(text) {
  const li = document.createElement('li');
  li.textContent = text;
  probeEl.appendChild(li);
}

async function test(url) {
  const t0 = performance.now();
  try {
    const r = await fetch(url, { cache: 'no-store' });
    const text = await r.text();
    add(url + ' -> HTTP ' + r.status + ' / ' + text.length + ' bytes / '
        + Math.round(performance.now() - t0) + 'ms');
  } catch (e) {
    add(url + ' -> 失败: ' + e.message);
  }
}

add('当前地址: ' + location.href);
add('浏览器在线状态: ' + (navigator.onLine ? '在线' : '离线'));
(async () => {
  await test('/api/v1/health');
  await test('/api/v1/health/ready');
  await test('/openapi.json');
  await test('/docs');
})();
</script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """服务总览页。"""
    return HTMLResponse(_INDEX_HTML, headers=_NO_STORE)


@router.get("/ui", response_class=HTMLResponse)
async def chat_ui() -> HTMLResponse:
    """内置聊天演示页。"""
    return HTMLResponse(_CHAT_HTML, headers=_NO_STORE)


def _render_doc_list() -> str:
    """服务端渲染接口列表，避免依赖前端脚本拉取 OpenAPI。"""
    from html import escape

    from app.main import app  # 延迟导入，避免模块级循环引用

    spec = app.openapi()
    groups: dict[str, list[str]] = {}
    for path, item in spec.get("paths", {}).items():
        for method, operation in item.items():
            tag = (operation.get("tags") or ["default"])[0]
            row = (
                f'<div class="ep" data-path="{escape(path)}" data-method="{method}">'
                f'<span class="m {method}">{method.upper()}</span>'
                f'<span class="p">{escape(path)}</span></div>'
            )
            groups.setdefault(tag, []).append(row)

    parts: list[str] = []
    for tag, rows in groups.items():
        parts.append(f'<div class="tag">{escape(tag)}</div>')
        parts.extend(rows)
    return "".join(parts)


@router.get("/docs", response_class=HTMLResponse)
async def offline_docs() -> HTMLResponse:
    """离线 API 文档：服务端渲染接口列表，不依赖任何 CDN。"""
    return HTMLResponse(_DOCS_HTML.replace("__SERVER_LIST__", _render_doc_list()), headers=_NO_STORE)


@router.get("/redoc", response_class=HTMLResponse)
async def offline_redoc() -> HTMLResponse:
    """ReDoc 依赖 CDN，离线环境下返回自包含文档页。"""
    return HTMLResponse(_DOCS_HTML.replace("__SERVER_LIST__", _render_doc_list()), headers=_NO_STORE)


@router.get("/swagger", response_class=HTMLResponse)
@router.get("/api-docs", response_class=HTMLResponse)
async def docs_alias() -> HTMLResponse:
    """/swagger、/api-docs 别名，等同 /docs（避免旧书签或习惯路径 404）。"""
    return HTMLResponse(_DOCS_HTML.replace("__SERVER_LIST__", _render_doc_list()), headers=_NO_STORE)


@router.get("/diag", response_class=HTMLResponse)
async def diagnostics(request: Request) -> HTMLResponse:
    """连通性诊断页：展示服务端看到的请求信息，并在浏览器端探测各接口可达性。"""
    info: dict[str, Any] = {
        "client_host": request.client.host if request.client else "unknown",
        "host_header": request.headers.get("host", ""),
        "user_agent": request.headers.get("user-agent", ""),
        "x_forwarded_for": request.headers.get("x-forwarded-for", ""),
        "server_time": datetime.now().isoformat(timespec="seconds"),
    }
    body = _DIAG_TEMPLATE.replace("__INFO__", json.dumps(info, ensure_ascii=False, indent=2))
    return HTMLResponse(body, headers=_NO_STORE)
