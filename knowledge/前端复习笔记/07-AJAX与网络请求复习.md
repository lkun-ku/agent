# AJAX 与网络请求复习

> AJAX 与网络请求是前端与服务器通信的核心技术。本文系统梳理 HTTP 基础、AJAX 原理（XMLHttpRequest）、axios 库的使用（拦截器、async/await）、fetch API、三者对比、跨域解决方案及 URL 参数处理等知识点。

## 一、HTTP 基础

### 1.1 HTTP 请求与响应

HTTP（HyperText Transfer Protocol）是基于请求-响应模型的应用层协议：客户端发送请求，服务端返回响应。

**HTTP 请求结构：**

```
POST /api/user HTTP/1.1          ← 请求行（方法 + URL + 版本）
Host: www.example.com             ← 请求头
Content-Type: application/json
Authorization: Bearer xxx

{"name":"张三","age":18}          ← 请求体（GET 一般没有）
```

**HTTP 响应结构：**

```
HTTP/1.1 200 OK                   ← 状态行（版本 + 状态码 + 状态描述）
Content-Type: application/json    ← 响应头
Content-Length: 42

{"code":0,"msg":"成功","data":{}} ← 响应体
```

| 组成部分 | 请求 | 响应 |
| --- | --- | --- |
| 起始行 | 请求行（方法 + URL） | 状态行（状态码） |
| 头部 | 请求头（headers） | 响应头（headers） |
| 主体 | 请求体（body） | 响应体（body） |

### 1.2 HTTP 请求方法

| 方法 | 说明 | 是否有请求体 | 幂等性 | 安全性 |
| --- | --- | --- | --- | --- |
| `GET` | 获取资源 | 否 | 是 | 是 |
| `POST` | 新增资源 | 是 | 否 | 否 |
| `PUT` | 完整更新资源 | 是 | 是 | 否 |
| `PATCH` | 局部更新资源 | 是 | 否 | 否 |
| `DELETE` | 删除资源 | 通常无 | 是 | 否 |

> 💡 **幂等性**：同一个请求执行多次和一次的效果相同。GET、PUT、DELETE 是幂等的，POST、PATCH 不是。

### 1.3 HTTP 状态码

| 分类 | 含义 | 常见状态码 |
| --- | --- | --- |
| 1xx | 信息性 | 100 Continue |
| 2xx | 成功 | 200 OK、201 Created |
| 3xx | 重定向 | 301 永久重定向、302 临时重定向、304 协商缓存命中 |
| 4xx | 客户端错误 | 400 参数错误、401 未认证、403 无权限、404 资源不存在、413 请求过大 |
| 5xx | 服务端错误 | 500 服务器内部错误、502 网关错误、503 服务不可用、504 网关超时 |

> ⚠️ **易错点**：`401`（未认证：没登录）与 `403`（无权限：登录了但没权限）容易混淆；`304` 不是错误，是浏览器缓存仍然有效。

### 1.4 常见请求头与响应头

| 头部字段 | 类型 | 说明 |
| --- | --- | --- |
| `Content-Type` | 请求/响应 | 数据类型，如 `application/json`、`application/x-www-form-urlencoded`、`multipart/form-data` |
| `Authorization` | 请求 | 携带身份凭证，如 `Bearer <token>` |
| `Accept` | 请求 | 客户端可接受的数据类型 |
| `Cookie` | 请求 | 携带 Cookie 信息 |
| `Set-Cookie` | 响应 | 服务端设置 Cookie |
| `Access-Control-Allow-Origin` | 响应 | CORS 跨域允许的源 |
| `Cache-Control` | 响应 | 缓存策略，如 `no-cache`、`max-age=3600` |

| Content-Type 值 | 使用场景 |
| --- | --- |
| `application/json` | 提交 JSON 数据（最常用） |
| `application/x-www-form-urlencoded` | 表单默认提交格式，`name=张三&age=18` |
| `multipart/form-data` | 文件上传 |
| `text/plain` | 纯文本 |

---

## 二、AJAX 原理

### 2.1 什么是 AJAX

AJAX（Asynchronous JavaScript And XML）是一套用于在不刷新整个页面的情况下与服务器通信的技术。

- **异步通信**：发送请求后不阻塞 JS 执行，通过回调接收结果
- **局部刷新**：只更新页面需要变化的部分
- **底层实现**：基于 `XMLHttpRequest`（XHR）对象

> 💡 现在的"AJAX"泛指所有异步网络请求技术，数据格式多为 JSON，已很少用 XML。

### 2.2 XMLHttpRequest 基本使用

```javascript
// 1. 创建 XHR 对象
const xhr = new XMLHttpRequest()

// 2. 配置请求（方法、URL、是否异步）
xhr.open('GET', 'https://api.example.com/user?id=1', true)

// 3. 监听响应事件（onreadystatechange）
xhr.onreadystatechange = function () {
  // readyState: 0 未初始化、1 已 open、2 已 send 收到头、3 加载中、4 完成
  if (xhr.readyState === 4) {
    if (xhr.status >= 200 && xhr.status < 300) {
      console.log('响应数据：', xhr.responseText)
    } else {
      console.error('请求失败：', xhr.status)
    }
  }
}

// 4. 发送请求（GET 不传参，POST 传 body）
xhr.send()
```

**使用 `onload` 简化（推荐）：**

```javascript
const xhr = new XMLHttpRequest()
xhr.open('POST', 'https://api.example.com/user', true)
xhr.setRequestHeader('Content-Type', 'application/json')

xhr.onload = function () {
  if (xhr.status >= 200 && xhr.status < 300) {
    console.log(JSON.parse(xhr.responseText))
  }
}

xhr.onerror = function () {
  console.error('网络错误')
}

// POST 请求体需要字符串化
xhr.send(JSON.stringify({ name: '张三', age: 18 }))
```

| XHR 属性/方法 | 说明 |
| --- | --- |
| `open(method, url, async)` | 初始化请求 |
| `send(body)` | 发送请求，GET 传 `null` |
| `setRequestHeader(key, value)` | 设置请求头（必须在 `open` 之后、`send` 之前） |
| `readyState` | 请求状态 0~4 |
| `status` | HTTP 状态码 |
| `responseText` | 响应文本（字符串） |
| `response` | 响应数据（可设置 `responseType`） |
| `onreadystatechange` | 状态变化事件 |
| `onload` | 请求完成事件 |
| `onerror` | 请求错误事件 |

> ⚠️ **易错点**：`setRequestHeader` 必须在 `open` 之后调用；`readyState === 4` 仅表示请求完成，不代表成功，还需判断 `status`。

### 2.3 使用 Promise 封装 XHR

原生 XHR 是基于回调的，使用 Promise 封装后可解决回调地狱，配合 `async/await` 更优雅：

```javascript
function myAxios({ url, method = 'GET', params = {}, data = {}, headers = {} }) {
  return new Promise((resolve, reject) => {
    // 1. 处理 GET 查询参数
    if (method.toUpperCase() === 'GET') {
      const qs = new URLSearchParams(params).toString()
      url += (url.includes('?') ? '&' : '?') + qs
    }

    // 2. 创建 XHR
    const xhr = new XMLHttpRequest()
    xhr.open(method.toUpperCase(), url, true)

    // 3. 设置请求头
    Object.keys(headers).forEach(key => {
      xhr.setRequestHeader(key, headers[key])
    })

    // 4. 监听响应
    xhr.onload = function () {
      if (xhr.status >= 200 && xhr.status < 300) {
        // 尝试解析 JSON
        try {
          resolve(JSON.parse(xhr.responseText))
        } catch {
          resolve(xhr.responseText)
        }
      } else {
        reject(new Error(`请求失败，状态码：${xhr.status}`))
      }
    }
    xhr.onerror = () => reject(new Error('网络错误'))

    // 5. 发送
    if (method.toUpperCase() === 'POST') {
      xhr.setRequestHeader('Content-Type', 'application/json')
      xhr.send(JSON.stringify(data))
    } else {
      xhr.send()
    }
  })
}

// 使用：then 链式调用
myAxios({ url: '/api/user', params: { id: 1 } })
  .then(res => console.log(res))
  .catch(err => console.error(err))

// 使用：async/await
async function getUser() {
  try {
    const res = await myAxios({ url: '/api/user', params: { id: 1 } })
    console.log(res)
  } catch (err) {
    console.error(err)
  }
}
```

> 💡 **Promise 封装的好处**：① 避免回调地狱 ② 支持链式调用 ③ 可配合 `async/await` 写同步风格代码 ④ 统一错误处理。

### 2.4 GET 与 POST 请求的区别

| 对比项 | GET | POST |
| --- | --- | --- |
| 参数位置 | URL 查询字符串 | 请求体 |
| 长度限制 | 有（浏览器限制约 2KB，HTTP 规范无限制） | 无 |
| 缓存 | 默认会被浏览器缓存 | 默认不缓存 |
| 安全性 | 较低（参数暴露在 URL、被历史记录保存） | 相对较高 |
| 幂等性 | 幂等 | 不幂等 |
| 历史记录 | 可保留参数 | 不保留 |
| 编码类型 | application/x-www-form-urlencoded | 多种（json/form-data 等） |
| 浏览器回退 | 无害 | 会再次提交请求 |

> ⚠️ **易错点**：GET 请求的参数会被浏览器、代理服务器缓存，可能导致数据不实时；提交敏感数据（密码、token）必须用 POST。

---

## 三、axios

### 3.1 axios 基本使用

axios 是基于 Promise 的 HTTP 客户端，浏览器端内部封装 XHR，Node 端使用 http 模块，支持请求/响应拦截器、自动 JSON 转换、错误处理等。

```javascript
// 通用配置写法
axios({
  url: '/api/user',
  method: 'GET',
  params: { id: 1 },          // GET 查询参数，自动拼接到 URL
  data: { name: '张三' },      // POST 请求体
  headers: { Authorization: 'Bearer xxx' }
}).then(res => {
  console.log(res.data)        // 响应数据
}).catch(err => {
  console.error(err)
})

// 快捷方法
axios.get('/api/user', { params: { id: 1 } })
axios.post('/api/user', { name: '张三' })   // 第二参数是 data
axios.put('/api/user/1', { name: '李四' })
axios.delete('/api/user/1')
```

> 💡 **易错点**：`axios.post(url, data, config)`，第二个参数是 `data`，第三个才是 `config`；而 `axios.get(url, config)`，第二个参数直接是 `config`。

### 3.2 请求配置

| 配置项 | 说明 | 示例 |
| --- | --- | --- |
| `url` | 请求地址 | `/api/user` |
| `method` | 请求方法（默认 GET） | `POST` |
| `baseURL` | 基础地址，会自动拼接 url | `https://api.example.com` |
| `params` | URL 查询参数（GET） | `{ id: 1 }` |
| `data` | 请求体（POST/PUT） | `{ name: '张三' }` |
| `headers` | 请求头 | `{ 'Content-Type': 'application/json' }` |
| `timeout` | 超时时间（ms） | `5000` |
| `responseType` | 响应数据类型 | `json`、`blob`、`text` |
| `withCredentials` | 是否携带 Cookie | `true` |

```javascript
axios({
  baseURL: 'https://api.example.com',
  url: '/api/user',
  method: 'POST',
  data: { name: '张三' },
  headers: { 'Content-Type': 'application/json' },
  timeout: 5000,
  responseType: 'json'
})
```

### 3.3 响应结构

axios 的 `then` 回调接收的不是一个普通对象，而是包装后的响应对象：

```javascript
axios.get('/api/user').then(res => {
  console.log(res)  // 响应对象
})
```

| 属性 | 说明 |
| --- | --- |
| `res.data` | **服务端返回的实际数据**（最常用，axios 已自动 JSON.parse） |
| `res.status` | HTTP 状态码 |
| `res.statusText` | 状态描述（如 `OK`） |
| `res.headers` | 响应头对象 |
| `res.config` | 本次请求的配置 |
| `res.request` | 生成该响应的 XHR 对象 |

> ⚠️ **易错点**：拿数据时是 `res.data`，不是直接 `res`，少写一个 `.data` 是新手最常犯的错。

### 3.4 拦截器

拦截器用于在请求发出前/响应返回后统一处理，避免在每个请求里重复写逻辑。

```javascript
// 请求拦截器：在请求发出前执行
axios.interceptors.request.use(
  config => {
    // 1. 自动注入 token
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    // 2. 开启 loading
    showLoading()
    return config        // 必须 return，否则请求发不出去
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器：在响应到达 then 之前执行
axios.interceptors.response.use(
  response => {
    // 1. 关闭 loading
    hideLoading()
    // 2. 统一处理业务码
    const { code, msg, data } = response.data
    if (code === 0) {
      return data        // 只把业务数据返回给 then
    }
    // token 过期，跳转登录
    if (code === 401) {
      location.href = '/login'
    }
    return Promise.reject(new Error(msg))
  },
  error => {
    hideLoading()
    // 3. 统一处理 HTTP 错误
    if (error.response) {
      const status = error.response.status
      if (status === 401) location.href = '/login'
      else if (status === 404) alert('资源不存在')
      else if (status >= 500) alert('服务器开小差了')
    } else if (error.code === 'ECONNABORTED') {
      alert('请求超时')
    }
    return Promise.reject(error)
  }
)
```

| 应用场景 | 用哪个拦截器 |
| --- | --- |
| 自动注入 token | 请求拦截器 |
| 开启/关闭 loading | 请求 + 响应拦截器 |
| 统一错误处理（状态码） | 响应拦截器 |
| 业务状态码判断 | 响应拦截器 |
| 请求参数格式化 | 请求拦截器 |

> 💡 **执行顺序**：对于多个请求拦截器，**后添加的先执行**（栈结构）；对于多个响应拦截器，**先添加的先执行**（队列结构）。

### 3.5 async/await 使用 axios

`async/await` 让异步代码看起来像同步代码，配合 `try/catch` 处理错误：

```javascript
// 1. 普通请求
async function getUser() {
  try {
    const res = await axios.get('/api/user', { params: { id: 1 } })
    console.log(res.data)
  } catch (err) {
    console.error('获取用户失败：', err.message)
  }
}

// 2. 串行请求（一个接一个）
async function getInfo() {
  const userRes = await axios.get('/api/user')
  const orderRes = await axios.get('/api/order', { params: { uid: userRes.data.id } })
  console.log(orderRes.data)
}

// 3. 并发请求（同时发出，等最慢的）
async function getList() {
  const [userRes, orderRes] = await Promise.all([
    axios.get('/api/user'),
    axios.get('/api/order')
  ])
  console.log(userRes.data, orderRes.data)
}
```

| 场景 | 写法 |
| --- | --- |
| 串行（有依赖关系） | `await` 依次调用 |
| 并发（无依赖） | `Promise.all([p1, p2])` |
| 任一成功即返回 | `Promise.race([p1, p2])` |
| 全部完成（无论成败） | `Promise.allSettled([p1, p2])` |

> ⚠️ **易错点**：`await` 只能在 `async` 函数内使用；忘记 `try/catch` 会导致错误被吞掉；多个无依赖请求串行 `await` 会浪费时间，应使用 `Promise.all`。

### 3.6 axios 创建实例

使用 `axios.create()` 创建带默认配置的实例，便于区分不同后端服务：

```javascript
// 创建实例
const http = axios.create({
  baseURL: 'https://api.example.com',
  timeout: 5000,
  headers: { 'Content-Type': 'application/json' }
})

// 添加拦截器（只作用于该实例）
http.interceptors.request.use(config => {
  config.headers.Authorization = `Bearer ${localStorage.getItem('token')}`
  return config
})

// 使用实例发请求
http.get('/user').then(res => console.log(res.data))

// 多个实例并存
const payHttp = axios.create({ baseURL: 'https://pay.example.com' })
const msgHttp  = axios.create({ baseURL: 'https://msg.example.com' })
```

| 对比 | 直接用 axios | 用 axios.create |
| --- | --- | --- |
| 默认配置 | 全局共享 | 实例独立 |
| 拦截器 | 全局生效 | 仅对实例生效 |
| 适用 | 单一后端 | 多个后端服务 |

> 💡 `axios.create()` 本质是对 `axios` 的一层封装，返回的实例与 `axios` 拥有相同 API。

---

## 四、fetch API

### 4.1 fetch 基本语法

`fetch` 是浏览器内置的网络请求 API，基于 Promise 设计，无需引入第三方库。

```javascript
// 基本语法
fetch(url, options).then(res => {
  // res 是 Response 对象，需要调用方法读取数据
  return res.json()    // 返回 Promise
}).then(data => {
  console.log(data)
}).catch(err => {
  console.error(err)
})
```

| Response 方法 | 说明 | 返回值 |
| --- | --- | --- |
| `res.json()` | 解析为 JSON 对象 | Promise |
| `res.text()` | 解析为纯文本 | Promise |
| `res.blob()` | 解析为二进制大对象（图片、文件） | Promise |
| `res.formData()` | 解析为 FormData | Promise |
| `res.arrayBuffer()` | 解析为 ArrayBuffer | Promise |
| `res.clone()` | 克隆响应（响应只能读一次） | Response |

| Response 属性 | 说明 |
| --- | --- |
| `res.ok` | 状态码 200~299 为 true |
| `res.status` | HTTP 状态码 |
| `res.statusText` | 状态描述 |
| `res.headers` | 响应头对象 |
| `res.url` | 响应的最终 URL |

> ⚠️ **易错点**：fetch **不会因为 404、500 而 reject**，只有网络错误才会进入 `catch`。必须手动检查 `res.ok`。

### 4.2 GET 请求

```javascript
// 1. 直接拼接查询字符串（不推荐）
fetch('https://api.example.com/user?id=1&name=张三')
  .then(res => res.json())

// 2. 使用 URLSearchParams 拼接（推荐）
const params = new URLSearchParams({ id: 1, name: '张三' })
fetch(`https://api.example.com/user?${params}`)
  .then(res => res.json())

// 3. 使用 URL 对象（更规范）
const url = new URL('https://api.example.com/user')
url.searchParams.set('id', 1)
url.searchParams.set('name', '张三')
fetch(url).then(res => res.json())

// 4. async/await 写法
async function getUser() {
  const params = new URLSearchParams({ id: 1 })
  const res = await fetch(`/api/user?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
```

### 4.3 POST 请求

**提交 JSON 数据：**

```javascript
async function addUser() {
  const res = await fetch('/api/user', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'    // 必须设置
    },
    body: JSON.stringify({ name: '张三', age: 18 })  // 必须字符串化
  })
  if (!res.ok) throw new Error('请求失败')
  return res.json()
}
```

**提交 FormData（文件上传）：**

```javascript
async function upload() {
  const fd = new FormData()
  fd.append('name', '张三')
  fd.append('avatar', fileInput.files[0])  // 文件对象

  const res = await fetch('/api/upload', {
    method: 'POST',
    body: fd
    // ⚠️ 不要手动设置 Content-Type！
    // 浏览器会自动加上 multipart/form-data; boundary=...
  })
  return res.json()
}
```

| 提交类型 | Content-Type | body 写法 |
| --- | --- | --- |
| JSON | `application/json` | `JSON.stringify(data)` |
| 表单 | `application/x-www-form-urlencoded` | `new URLSearchParams(data)` |
| 文件上传 | `multipart/form-data`（自动） | `new FormData()` |
| 纯文本 | `text/plain` | 字符串 |

> ⚠️ **易错点**：提交 FormData 时**不要手动设置** `Content-Type`，因为 `multipart/form-data` 需要带 `boundary` 边界标识，由浏览器自动生成。

### 4.4 fetch 与 axios 的区别

| 对比项 | fetch | axios |
| --- | --- | --- |
| 来源 | 浏览器原生 API | 第三方库（基于 XHR） |
| 404/500 错误 | 不 reject，需手动检查 `res.ok` | 自动 reject，进入 catch |
| 自动 JSON | 否，需手动 `res.json()` | 是，自动解析 `res.data` |
| 请求超时 | 不支持，需用 `AbortController` | 支持 `timeout` 配置 |
| 拦截器 | 无内置，需手动封装 | 内置 |
| Cookie | 默认不携带 | 通过 `withCredentials` 配置 |
| 取消请求 | `AbortController` | `CancelToken` / `AbortController` |
| 请求进度 | 支持（上传下载） | 支持上传进度 |
| 兼容性 | 较新（IE 不支持） | 兼容 IE |

```javascript
// fetch 处理错误的正确姿势
fetch('/api/user')
  .then(res => {
    if (!res.ok) {
      throw new Error(`HTTP 错误：${res.status}`)
    }
    return res.json()
  })
  .then(data => console.log(data))
  .catch(err => console.error(err))  // 网络错误 或 抛出的错误都会进这里

// fetch 携带 Cookie
fetch('/api/user', {
  credentials: 'include'   // 跨域携带 Cookie
  // 'same-origin'：同源携带；'omit'：不携带（默认）
})
```

```javascript
// fetch 实现请求超时
function fetchWithTimeout(url, options = {}, timeout = 5000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(timer))
}
```

> 💡 **面试重点**：fetch 的设计哲学是"低层 API"，把控制权交给开发者，所以错误处理、超时、拦截等都需要自己实现；axios 是"高层封装"，开箱即用。

---

## 五、ajax / axios / fetch 对比

| 对比项 | ajax（XHR） | axios | fetch |
| --- | --- | --- | --- |
| 本质 | 原生 JS 技术 | Promise HTTP 库 | 浏览器内置 API |
| 底层实现 | XMLHttpRequest | 浏览器端封装 XHR | 浏览器原生 |
| Promise 支持 | 不支持（回调） | 支持 | 原生支持 |
| 拦截器 | 无 | 有 | 无 |
| 自动 JSON 转换 | 否 | 是 | 否 |
| 自动错误处理 | 否 | 是（4xx/5xx 自动 reject） | 否（需检查 res.ok） |
| 请求超时 | 通过 `xhr.timeout` | `timeout` 配置 | `AbortController` |
| 取消请求 | `xhr.abort()` | `CancelToken` | `AbortController` |
| 跨域携带 Cookie | `withCredentials` | `withCredentials` | `credentials` |
| 适用场景 | 学习原理 | 项目开发 | 简单项目/现代框架 |

**演进关系：**

```
XMLHttpRequest（原生，回调风格）
       │
       ├── axios（封装 XHR，Promise 风格，功能丰富）
       │
       └── fetch（浏览器新标准，原生 Promise，更底层）
```

> 💡 **选型建议**：学习阶段先掌握 XHR 理解原理；实际项目开发用 axios（功能齐全、生态成熟）；轻量项目或追求原生可用 fetch。

---

## 六、跨域

### 6.1 同源策略

**同源策略**是浏览器的安全机制，限制一个源的脚本与另一个源的资源交互。**同源**指协议（protocol）、域名（host）、端口（port）三者完全相同。

| URL | 与 `http://www.example.com/a.html` 的关系 |
| --- | --- |
| `http://www.example.com/b.html` | 同源 |
| `https://www.example.com/a.html` | 不同源（协议不同） |
| `http://api.example.com/a.html` | 不同源（域名不同） |
| `http://www.example.com:8080/a.html` | 不同源（端口不同） |

> ⚠️ **易错点**：跨域限制是**浏览器**的行为，服务端之间通信不存在跨域；跨域请求其实**发出去了**，只是响应被浏览器拦截了。

### 6.2 跨域解决方案

#### 1. CORS（服务端解决，最常用）

服务端设置响应头 `Access-Control-Allow-Origin`：

```http
// 允许所有源访问
Access-Control-Allow-Origin: *

// 允许指定源
Access-Control-Allow-Origin: https://www.example.com

// 允许携带 Cookie 时必须指定具体源，且设置
Access-Control-Allow-Credentials: true
```

**简单请求 vs 预检请求：**

| 类型 | 触发条件 | 流程 |
| --- | --- | --- |
| 简单请求 | GET/POST/HEAD + 常见 Content-Type + 常见请求头 | 直接发送请求 |
| 预检请求（OPTIONS） | PUT/DELETE、自定义头、`application/json` | 先发 OPTIONS 探测，通过后再发真实请求 |

#### 2. 代理服务器（开发常用）

前端无法控制服务端时，开发环境通过代理转发请求：

```javascript
// vue.config.js
module.exports = {
  devServer: {
    proxy: {
      '/api': {
        target: 'https://api.example.com',  // 目标地址
        changeOrigin: true,                  // 改变源
        pathRewrite: { '^/api': '' }         // 重写路径
      }
    }
  }
}

// vite.config.js
export default {
  server: {
    proxy: {
      '/api': {
        target: 'https://api.example.com',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api/, '')
      }
    }
  }
}
```

> 💡 **原理**：同源策略只限制浏览器，代理服务器之间通信不受限制。前端请求同源的 `/api`，由 devServer 转发到目标服务器。

#### 3. JSONP（仅支持 GET，已过时）

利用 `<script>` 标签没有跨域限制的特性：

```html
<script>
// 前端定义回调函数
function handleData(data) {
  console.log(data)
}
</script>
<!-- 服务端返回 handleData({...}) 形式 -->
<script src="https://api.example.com/user?callback=handleData"></script>
```

| 方案 | 支持方法 | 是否需要服务端配合 | 使用场景 |
| --- | --- | --- | --- |
| CORS | 所有 | 是 | 生产环境首选 |
| 代理服务器 | 所有 | 否 | 开发环境 |
| JSONP | 仅 GET | 是 | 已基本淘汰 |

---

## 七、URL 与参数处理

### 7.1 URL 结构

```
https://www.example.com:443/api/user?id=1&name=张三#detail
\___/   \______________/\_/\______/\_______________/\____/
  |            |        |     |          |            |
协议 protocol  host     port  path      query        hash
```

| 组成 | 说明 | 示例 |
| --- | --- | --- |
| protocol | 协议 | `https:` |
| host | 主机名（域名） | `www.example.com` |
| port | 端口（https 默认 443，http 默认 80） | `443` |
| path | 路径 | `/api/user` |
| query | 查询字符串 | `?id=1&name=张三` |
| hash | 锚点（前端路由用） | `#detail` |

### 7.2 URLSearchParams

`URLSearchParams` 用于处理查询字符串，无需手动拼接 `&` 和 `=`：

```javascript
const params = new URLSearchParams()

// 1. 追加参数
params.append('name', '张三')
params.append('age', 18)

// 2. 设置（覆盖同名参数）
params.set('age', 20)

// 3. 获取
params.get('name')      // '张三'
params.has('name')       // true

// 4. 删除
params.delete('age')

// 5. 转字符串
params.toString()        // 'name=张三'

// 6. 遍历
for (const [key, value] of params) {
  console.log(key, value)
}

// 从字符串构造
const p = new URLSearchParams('id=1&name=张三')
p.get('id')  // '1'
```

### 7.3 URL 编码

URL 中不允许出现中文、空格、特殊字符（如 `&`、`=`、`#`），需进行编码：

```javascript
// 编码：将特殊字符转为 %XX 形式
encodeURIComponent('张三 & 李四')   // '张三%20%26%20李四'
encodeURIComponent('a/b?c=d')      // 'a%2Fb%3Fc%3Dd'

// 解码
decodeURIComponent('%E5%BC%A0%E4%B8%89')  // '张三'

// URLSearchParams 和 axios 会自动编码，无需手动处理
new URLSearchParams({ name: '张三' }).toString()  // 'name=%E5%BC%A0%E4%B8%89'
```

| 函数 | 编码范围 | 使用场景 |
| --- | --- | --- |
| `encodeURI` | 不编码 `:/?#[]@!$&'()*+,;=` | 编码整个 URL |
| `encodeURIComponent` | 不编码 `A-Z a-z 0-9 - _ . ! ~ * ' ( )` | 编码参数值（推荐） |
| `decodeURI` | 解码 `encodeURI` | 配对使用 |
| `decodeURIComponent` | 解码 `encodeURIComponent` | 配对使用 |

> ⚠️ **易错点**：编码参数值用 `encodeURIComponent`，不要用 `encodeURI`，否则参数中的 `&`、`=` 不会被编码，导致解析错乱。实际开发中 `URLSearchParams` 和 axios 会自动处理编码，很少需要手动调用。

---

## 💡 关联面试题

**Q1：AJAX 原理是什么？XMLHttpRequest 的工作流程？**
- AJAX 是基于 XHR 实现的异步通信技术，无需刷新页面即可与服务器交互
- XHR 流程：① `new XMLHttpRequest()` 创建对象 ② `open(method, url, async)` 初始化 ③ `setRequestHeader` 设置请求头 ④ 监听 `onreadystatechange` 或 `onload` 事件 ⑤ `send(body)` 发送请求 ⑥ 在回调中读取 `responseText`/`response`

**Q2：axios 拦截器的作用？执行顺序？**
- 作用：在请求发出前/响应返回后统一处理，如 token 注入、loading 控制、错误处理、业务码判断
- 执行顺序：请求拦截器**后添加的先执行**（栈）；响应拦截器**先添加的先执行**（队列）
- 流程：请求拦截器 → 发请求 → 响应拦截器 → then/catch

**Q3：fetch 和 axios 有什么区别？**
- fetch 是浏览器原生 API，axios 是第三方库（封装 XHR）
- fetch 不会因 4xx/5xx 自动 reject，需手动检查 `res.ok`；axios 会自动进入 catch
- fetch 不自动解析 JSON，需手动 `res.json()`；axios 自动解析到 `res.data`
- fetch 无内置拦截器、超时配置；axios 都有
- fetch 跨域默认不携带 Cookie，需 `credentials: 'include'`

**Q4：GET 和 POST 请求的区别？**
- 参数位置：GET 在 URL 查询串，POST 在请求体
- 长度限制：GET 有（浏览器限制），POST 几乎无
- 安全性：GET 参数暴露在 URL，POST 相对安全
- 缓存：GET 默认缓存，POST 不缓存
- 幂等性：GET 幂等，POST 不幂等

**Q5：什么是跨域？如何解决？**
- 跨域是浏览器同源策略限制：协议、域名、端口任一不同即为跨域
- 解决方案：① CORS（服务端设置 `Access-Control-Allow-Origin`，生产首选）② 代理服务器（开发环境 devServer.proxy）③ JSONP（仅 GET，已淘汰）

**Q6：HTTP 常见状态码有哪些？**
- 2xx 成功：200 OK、201 Created
- 3xx 重定向：301 永久重定向、302 临时重定向、304 协商缓存命中
- 4xx 客户端错误：400 参数错误、401 未认证、403 无权限、404 资源不存在
- 5xx 服务端错误：500 内部错误、502 网关错误、503 服务不可用、504 网关超时

**Q7：Promise 封装 AJAX 的好处？**
- 避免回调地狱，代码扁平化
- 支持链式调用 `.then().then()`
- 可配合 `async/await` 写同步风格代码
- 统一错误处理（`.catch`）
- 便于扩展拦截器逻辑
