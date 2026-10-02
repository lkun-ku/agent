# Node.js 与工程化复习

> 前端工程化是提升开发效率和代码质量的关键。本文档系统梳理 Node.js 运行时、核心模块、Express 框架、中间件机制、MySQL 数据库、身份认证（JWT）、npm 包管理、Webpack/Vite 构建工具及 Git 版本控制。

## 一、Node.js 基础

### 1.1 Node.js 是什么

Node.js 是基于 Chrome V8 引擎的 JavaScript 运行时，使 JavaScript 能在服务端运行。

```bash
# 查看版本
node -v

# 执行 JS 文件
node app.js

# 进入 REPL 交互环境
node
```

### 1.2 Node.js 与浏览器 JS 的区别

| 对比项 | 浏览器 JS | Node.js |
| --- | --- | --- |
| 运行环境 | 浏览器 | 操作系统 |
| 顶层对象 | `window` | `global`（Node 18+ 也支持 `globalThis`） |
| DOM/BOM | 有 | 无 |
| 文件系统 | 不能操作 | 可通过 `fs` 模块操作 |
| 网络 | 受浏览器限制 | 可创建 HTTP 服务器 |
| 模块系统 | ES Module | CommonJS（默认）/ ES Module |

> ⚠️ **易错点**：Node.js 中没有 `window`、`document`、`localStorage` 等浏览器 API，直接使用会报 `ReferenceError`。

### 1.3 模块系统

#### CommonJS

```javascript
// math.js - 导出模块
function add(a, b) { return a + b }
module.exports = { add }
// exports.add = add  // 等价写法

// app.js - 导入模块
const { add } = require('./math')
console.log(add(1, 2)) // 3
```

#### ES Module

```javascript
// math.js
export function add(a, b) { return a + b }
export default function multiply(a, b) { return a * b }

// app.js
import multiply, { add } from './math.js'
```

| 对比 | CommonJS | ES Module |
| --- | --- | --- |
| 语法 | `require` / `module.exports` | `import` / `export` |
| 加载 | 运行时加载（同步） | 编译时确定（静态） |
| 输出 | 值的拷贝 | 值的引用 |
| 适用 | Node.js 默认 | 浏览器 / Node.js（新） |

### 1.4 全局对象

| 对象 | 说明 |
| --- | --- |
| `global` | 全局对象（类似浏览器的 window） |
| `process` | 进程对象（env、argv、exit） |
| `__dirname` | 当前文件所在目录的绝对路径 |
| `__filename` | 当前文件的绝对路径 |
| `Buffer` | 二进制数据缓冲区 |

> ⚠️ `__dirname` 和 `__filename` 在 ES Module 中不可用，需用 `import.meta.url` 替代。

---

## 二、Node.js 核心模块

### 2.1 fs 文件系统模块

```javascript
const fs = require('fs')
const path = require('path')

// 异步读取
fs.readFile(path.join(__dirname, '1.txt'), 'utf8', (err, data) => {
  if (err) return console.log('读取失败：', err.message)
  console.log('读取成功：', data)
})

// 同步读取
const data = fs.readFileSync('./1.txt', 'utf8')

// 写入文件（覆盖）
fs.writeFile('./2.txt', 'hello', err => {
  if (err) return console.log('写入失败')
  console.log('写入成功')
})

// 追加写入
fs.appendFile('./2.txt', '\nworld', err => {})
```

| 方法 | 说明 |
| --- | --- |
| `fs.readFile` / `readFileSync` | 读取文件 |
| `fs.writeFile` / `writeFileSync` | 写入文件（覆盖） |
| `fs.appendFile` | 追加内容 |
| `fs.unlink` | 删除文件 |
| `fs.mkdir` | 创建目录 |
| `fs.readdir` | 读取目录 |

### 2.2 path 路径模块

```javascript
const path = require('path')

path.join('/a', 'b', 'c')        // /a/b/c（拼接路径）
path.resolve('a', 'b')           // /当前目录/a/b（解析为绝对路径）
path.basename('/a/b/c.txt')      // c.txt（文件名）
path.dirname('/a/b/c.txt')       // /a/b（目录名）
path.extname('/a/b/c.txt')       // .txt（扩展名）
```

> ⚠️ 拼接路径时推荐用 `path.join()`，避免手动用 `+` 拼接导致路径分隔符问题。

### 2.3 http 模块

```javascript
const http = require('http')

const server = http.createServer((req, res) => {
  // req：请求对象（req.url、req.method）
  // res：响应对象
  res.setHeader('Content-Type', 'text/html; charset=utf-8')
  res.end('Hello World')
})

server.listen(3000, () => {
  console.log('服务器启动：http://127.0.0.1:3000')
})
```

### 2.4 url 与 querystring 模块

```javascript
const url = require('url')
const qs = require('querystring')

const { pathname, query } = url.parse(req.url, true)
// query 已解析为对象：{ name: 'jack', age: '18' }
```

---

## 三、Express 框架（重点）

### 3.1 Express 简介

Express 是 Node.js 最流行的 Web 开发框架，提供简洁的路由和中间件机制。

```bash
npm i express
```

### 3.2 基本使用

```javascript
const express = require('express')
const app = express()

// GET 路由
app.get('/', (req, res) => {
  res.send('Hello Express')
})

// POST 路由
app.post('/api/add', (req, res) => {
  res.send({ code: 0, msg: '添加成功' })
})

// 动态参数路由
app.get('/user/:id', (req, res) => {
  res.send(`用户ID：${req.params.id}`)
})

// 查询参数
app.get('/search', (req, res) => {
  res.send(`关键词：${req.query.keyword}`)
})

app.listen(3000, () => {
  console.log('Express 服务器启动')
})
```

### 3.3 req 与 res 常用属性方法

| 对象 | 属性/方法 | 说明 |
| --- | --- | --- |
| `req` | `req.query` | GET 查询参数（对象） |
| `req.params` | 动态路由参数 |
| `req.body` | POST 请求体（需中间件解析） |
| `res` | `res.send()` | 发送响应 |
| | `res.json()` | 发送 JSON 响应 |
| | `res.sendFile()` | 发送文件 |
| | `res.redirect()` | 重定向 |
| | `res.status()` | 设置状态码 |

### 3.4 静态资源托管

```javascript
// 将 public 目录下的文件作为静态资源对外提供
app.use(express.static('public'))

// 访问 http://localhost:3000/img/logo.png 即可获取 public/img/logo.png
```

### 3.5 模块化路由

```javascript
// router/user.js
const express = require('express')
const router = express.Router()

router.get('/list', (req, res) => { res.send('用户列表') })
router.post('/add', (req, res) => { res.send('添加用户') })

module.exports = router

// app.js
const userRouter = require('./router/user')
app.use('/api/user', userRouter)
// 访问 /api/user/list
```

---

## 四、中间件机制（重点）

### 4.1 什么是中间件

中间件是处理请求的函数，可以访问 `req` 和 `res`，通过 `next()` 将控制权交给下一个中间件。

```
请求 → 全局中间件1 → 全局中间件2 → 路由 → 路由中间件 → 响应
```

### 4.2 全局中间件

```javascript
// 每个请求都会经过
app.use((req, res, next) => {
  console.log('全局中间件：', req.method, req.url)
  next() // 必须调用 next()，否则请求会卡住
})

// 可定义多个全局中间件，按顺序执行
app.use((req, res, next) => {
  console.log('第二个全局中间件')
  next()
})
```

### 4.3 局部中间件

```javascript
// 只对特定路由生效
const mw = (req, res, next) => {
  console.log('局部中间件')
  next()
}

app.get('/test', mw, (req, res) => {
  res.send('OK')
})

// 多个局部中间件
app.get('/test2', mw1, mw2, (req, res) => {})
app.get('/test2', [mw1, mw2], (req, res) => {})
```

### 4.4 中间件分类

| 类型 | 说明 | 示例 |
| --- | --- | --- |
| 全局中间件 | 所有请求都经过 | `app.use(fn)` |
| 局部中间件 | 特定路由经过 | `app.get('/x', fn, handler)` |
| 错误中间件 | 捕获错误 | `(err, req, res, next) => {}` |
| 内置中间件 | Express 自带 | `express.static`、`express.json`、`express.urlencoded` |
| 第三方中间件 | npm 安装 | `cors`、`morgan` |

### 4.5 内置中间件

```javascript
// 解析 JSON 请求体
app.use(express.json())

// 解析 URL-encoded 请求体
app.use(express.urlencoded({ extended: false }))
```

### 4.6 错误级别中间件

```javascript
// 必须放在所有路由之后
app.use((err, req, res, next) => {
  console.error(err.message)
  res.status(500).send({ code: 500, msg: '服务器内部错误' })
})
```

### 4.7 自定义中间件示例

```javascript
// 自定义表单解析中间件
const customBodyParser = (req, res, next) => {
  let data = ''
  req.on('data', chunk => { data += chunk })
  req.on('end', () => {
    req.body = qs.parse(data)
    next()
  })
}
app.use(customBodyParser)
```

### 4.8 常用第三方中间件

| 中间件 | 作用 |
| --- | --- |
| `cors` | 解决跨域 |
| `morgan` | 日志记录 |
| `body-parser` | 解析请求体（已内置） |
| `multer` | 文件上传 |
| `express-jwt` | JWT 解析 |

---

## 五、MySQL 数据库

### 5.1 MySQL 基础

```sql
-- 创建数据库
CREATE DATABASE IF NOT EXISTS `my_db` DEFAULT CHARSET utf8mb4;

-- 创建表
CREATE TABLE `users` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `username` VARCHAR(255) NOT NULL,
  `password` VARCHAR(255) NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 增
INSERT INTO `users` (`username`, `password`) VALUES ('admin', '123456');

-- 删
DELETE FROM `users` WHERE `id` = 1;

-- 改
UPDATE `users` SET `password` = '654321' WHERE `id` = 1;

-- 查
SELECT * FROM `users`;
SELECT `id`, `username` FROM `users` WHERE `id` = 1;
```

### 5.2 Node.js 操作 MySQL

```bash
npm i mysql
```

```javascript
const mysql = require('mysql')

// 创建连接
const db = mysql.createPool({
  host: '127.0.0.1',
  user: 'root',
  password: '123456',
  database: 'my_db'
})

// 查询
db.query('SELECT * FROM users', (err, results) => {
  if (err) return console.log(err.message)
  console.log(results)
})

// 插入（占位符防 SQL 注入）
const user = { username: 'jack', password: '888' }
db.query('INSERT INTO users SET ?', user, (err, results) => {
  if (err) return console.log(err.message)
  console.log('插入成功，ID：', results.insertId)
})

// 更新
db.query('UPDATE users SET ? WHERE id = ?', [{ password: '999' }, 1], (err, results) => {})

// 删除
db.query('DELETE FROM users WHERE id = ?', 1, (err, results) => {})
})
```

> ⚠️ 使用 `?` 占位符可防止 SQL 注入，永远不要直接拼接 SQL 字符串。

### 5.3 Promise 封装 MySQL 查询

```javascript
function query(sql, params) {
  return new Promise((resolve, reject) => {
    db.query(sql, params, (err, results) => {
      if (err) reject(err)
      else resolve(results)
    })
  })
}

// 使用 async/await
async function getUsers() {
  try {
    const users = await query('SELECT * FROM users')
    console.log(users)
  } catch (err) {
    console.log(err)
  }
}
```

---

## 六、身份认证

### 6.1 Session 认证

```bash
npm i express-session
```

```javascript
const session = require('express-session')

app.use(session({
  secret: 'keyboard cat',
  resave: false,
  saveUninitialized: true
}))

// 登录时存入 session
app.post('/login', (req, res) => {
  if (验证通过) {
    req.session.user = userInfo
    req.session.isLogin = true
    res.send('登录成功')
  }
})

// 访问受保护资源时检查
app.get('/user', (req, res) => {
  if (!req.session.isLogin) {
    return res.redirect('/login')
  }
  res.send('用户信息')
})

// 退出登录
app.post('/logout', (req, res) => {
  req.session.destroy()
  res.send('退出成功')
})
```

### 6.2 JWT 认证（推荐）

JWT（JSON Web Token）是无状态的认证方案，适合前后端分离。

```bash
npm i jsonwebtoken express-jwt
```

```javascript
const jwt = require('jsonwebtoken')
const { expressjwt: expressJWT } = require('express-jwt')

const secretKey = 'itheima No1 ^_^'

// 注册 JWT 解析中间件（unless 指定不需要 token 的接口）
app.use(expressJWT({ secret: secretKey, algorithms: ['HS256'] })
  .unless({ path: [/^\/api\//] }))

// 登录成功后生成 token
app.post('/login', (req, res) => {
  // 验证用户名密码...
  const token = jwt.sign({ username: userInfo.username }, secretKey, {
    expiresIn: '2h' // 过期时间
  })
  res.send({ code: 0, msg: '登录成功', token })
})

// 受保护接口可直接使用 req.user
app.get('/user/info', (req, res) => {
  res.send({ code: 0, msg: '成功', data: req.user })
})

// 捕获 JWT 错误
app.use((err, req, res, next) => {
  if (err.name === 'UnauthorizedError') {
    return res.send({ code: 401, msg: '无效的 token' })
  }
  res.send({ code: 500, msg: '未知错误' })
})
```

### 6.3 Session vs JWT

| 对比 | Session | JWT |
| --- | --- | --- |
| 存储位置 | 服务端 | 客户端 |
| 状态 | 有状态 | 无状态 |
| 扩展性 | 差（需共享 session） | 好 |
| 适用场景 | 传统网页 | 前后端分离、移动端、API |
| 安全性 | 较高（信息在服务端） | 中（token 可解码） |

---

## 七、API 服务器项目架构

### 7.1 项目结构

```
api_server/
├── app.js              # 入口文件
├── config.js           # 配置（密钥等）
├── db/
│   └── index.js        # 数据库连接
├── router/
│   ├── user.js         # 用户路由
│   └── userinfo.js     # 用户信息路由
├── router_handler/
│   ├── user.js         # 路由处理函数
│   └── userinfo.js
├── schema/
│   └── user.js         # 数据校验规则
└── uploads/            # 上传文件目录
```

### 7.2 分层架构

```
路由层（router）  →  路由处理层（router_handler）  →  数据库层（db）
     ↑                    ↑                              ↑
  定义路由          业务逻辑处理                    数据库操作
```

```javascript
// router/user.js - 路由定义
router.post('/login', userHandler.login)

// router_handler/user.js - 处理函数
exports.login = (req, res) => {
  // 业务逻辑
  // 数据库查询
  // 返回结果
}
```

### 7.3 数据校验 @escook/express-joi

```javascript
const expressJoi = require('@escook/express-joi')
const schema = require('../schema/user')

// 注册时校验（自动校验、校验失败自动抛出错误）
router.post('/reguser', expressJoi(schema.reg_login_schema), userHandler.regUser)
```

### 7.4 文件上传 multer

```javascript
const multer = require('multer')
const upload = multer({ dest: './uploads' })

// 单文件上传
app.post('/upload', upload.single('avatar'), (req, res) => {
  res.send({ url: `http://localhost:3000/${req.file.path}` })
})
```

### 7.5 密码加密 bcryptjs

```javascript
const bcrypt = require('bcryptjs')

// 加密
const hashedPwd = bcrypt.hashSync('123456', 10)

// 比对
const isMatch = bcrypt.compareSync('123456', hashedPwd)
```

---

## 八、npm 包管理

### 8.1 npm 命令

```bash
npm init -y              # 初始化项目
npm install              # 安装所有依赖
npm i axios              # 安装生产依赖
npm i -D webpack         # 安装开发依赖
npm i -g nodemon         # 全局安装
npm uninstall axios      # 卸载
npm run dev              # 运行脚本
npm list                 # 查看已安装依赖
```

### 8.2 package.json 关键字段

```json
{
  "name": "my-project",
  "version": "1.0.0",
  "main": "app.js",
  "scripts": {
    "dev": "nodemon app.js",
    "start": "node app.js"
  },
  "dependencies": {        // 生产依赖
    "express": "^4.17.1"
  },
  "devDependencies": {     // 开发依赖
    "nodemon": "^2.0.12"
  }
}
```

### 8.3 语义化版本号

| 符号 | 含义 | 示例 |
| --- | --- | --- |
| `^` | 允许小版本更新 | `^1.2.3` → 1.x.x |
| `~` | 允许补丁更新 | `~1.2.3` → 1.2.x |
| 无 | 精确版本 | `1.2.3` |

### 8.4 dependencies vs devDependencies

| 对比 | dependencies | devDependencies |
| --- | --- | --- |
| 环境 | 生产环境 | 开发环境 |
| 示例 | express、axios | webpack、nodemon |
| npm i --production | 安装 | 不安装 |

### 8.5 package-lock.json

锁定依赖的精确版本，保证团队成员安装版本一致。

### 8.6 npx

```bash
# 直接执行 node_modules 中的命令，无需全局安装
npx webpack
npx create-react-app my-app
```

### 8.7 发布 npm 包

```bash
npm login        # 登录
npm publish      # 发布
npm version patch # 更新补丁版本号
npm unpublish    # 撤销发布（72小时内）
```

---

## 九、Webpack 构建工具

### 9.1 Webpack 是什么

Webpack 是静态模块打包器，将各种资源（JS、CSS、图片等）打包为浏览器可识别的文件。

### 9.2 核心概念

| 概念 | 说明 |
| --- | --- |
| Entry | 入口文件 |
| Output | 输出配置 |
| Loader | 处理非 JS 文件（转换器） |
| Plugin | 扩展功能（插件） |
| Mode | `development` / `production` |

### 9.3 基本配置

```javascript
const path = require('path')
const HtmlWebpackPlugin = require('html-webpack-plugin')

module.exports = {
  mode: 'development',
  entry: './src/main.js',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.[hash:8].js'
  },
  module: {
    rules: [
      { test: /\.css$/, use: ['style-loader', 'css-loader'] },
      { test: /\.js$/, exclude: /node_modules/, use: 'babel-loader' },
      { test: /\.(png|jpg|gif)$/, type: 'asset/resource' }
    ]
  },
  plugins: [
    new HtmlWebpackPlugin({ template: './public/index.html' })
  ],
  devServer: {
    port: 3000,
    open: true,
    proxy: { '/api': { target: 'http://localhost:8080', changeOrigin: true } }
  }
}
```

### 9.4 常用 Loader

| Loader | 作用 |
| --- | --- |
| `babel-loader` | ES6+ → ES5 |
| `css-loader` | 解析 CSS 的 import |
| `style-loader` | 将 CSS 注入 DOM |
| `sass-loader` / `less-loader` | 预处理器编译 |
| `file-loader` / `url-loader` | 处理图片资源 |
| `postcss-loader` | CSS 后处理（autoprefixer） |

> ⚠️ Loader 执行顺序：**从右到左、从下到上**。

### 9.5 Loader 与 Plugin 的区别

| 对比 | Loader | Plugin |
| --- | --- | --- |
| 作用 | 转换文件 | 扩展功能 |
| 本质 | 转换器 | 插件对象 |
| 配置 | module.rules | plugins 数组 |
| 示例 | babel-loader | HtmlWebpackPlugin |

### 9.6 开发服务器 webpack-dev-server

- 支持热更新 HMR（Hot Module Replacement）
- 代码变化自动刷新
- 配置 proxy 代理解决跨域

### 9.7 Vite 简介

Vite 是下一代构建工具，基于 ES Module，开发时极速启动。

| 对比 | Webpack | Vite |
| --- | --- | --- |
| 启动速度 | 慢（打包后启动） | 极快（按需加载） |
| HMR | 全量更新 | 精确模块更新 |
| 构建 | 自带打包 | 基于 Rollup |
| 适用 | 复杂项目 | 现代项目（推荐） |

---

## 十、Babel

### 10.1 Babel 是什么

Babel 是 JavaScript 编译器，将 ES6+ 代码转换为 ES5，使新语法能在旧浏览器运行。

### 10.2 配置

```json
// .babelrc
{
  "presets": [
    ["@babel/preset-env", {
      "targets": { "ie": 11 },
      "useBuiltIns": "usage",
      "corejs": 3
    }]
  ],
  "plugins": []
}
```

### 10.3 preset-env 与 plugin

| 概念 | 说明 |
| --- | --- |
| `preset-env` | 预设插件集合（ES6+ 转换） |
| `plugin` | 单个语法转换插件 |
| `useBuiltIns: 'usage'` | 按需引入 polyfill |

---

## 十一、Git 版本控制

### 11.1 Git 基本概念

```
工作区 ──git add──→ 暂存区 ──git commit──→ 版本库 ──git push──→ 远程仓库
```

### 11.2 常用命令

```bash
# 初始化
git init
git clone <url>

# 基本操作
git status              # 查看状态
git add .               # 添加到暂存区
git add <file>          # 添加指定文件
git commit -m "描述"     # 提交到版本库
git push origin main    # 推送到远程
git pull origin main    # 拉取远程更新

# 查看
git log                 # 查看提交历史
git log --oneline       # 简洁模式
git diff                # 查看工作区与暂存区差异
git diff --cached       # 查看暂存区与版本库差异

# 撤销
git restore <file>      # 撤销工作区修改
git restore --staged <file> # 撤销暂存
git reset --hard HEAD~1 # 回退到上一个版本（危险）

# 分支
git branch              # 查看分支
git branch dev          # 创建分支
git checkout dev        # 切换分支
git checkout -b dev     # 创建并切换
git merge dev           # 合并 dev 到当前分支
git branch -d dev       # 删除分支
```

### 11.3 分支管理策略

```
main ────────●──────────────●─────── 稳定版本
           \              /
dev ────────●──●──●──●──●──────────── 开发分支
              \      /
feature/xxx ───●──●──●────────────── 功能分支
```

- `main`/`master`：生产分支，只合并稳定代码
- `develop`：开发分支
- `feature/*`：功能分支
- `hotfix/*`：紧急修复分支

### 11.4 merge vs rebase

| 对比 | merge | rebase |
| --- | --- | --- |
| 结果 | 保留分叉历史 | 线性历史 |
| 冲突 | 一次性解决 | 可能多次解决 |
| 安全性 | 安全 | 禁止对公共分支使用 |

> ⚠️ **黄金法则**：永远不要在公共分支（main、develop）上使用 rebase。

### 11.5 远程协作

```bash
git remote add origin <url>    # 关联远程仓库
git push -u origin main        # 首次推送并建立关联
git remote -v                  # 查看远程仓库
git fetch origin               # 获取远程更新（不合并）
git pull origin main           # 获取并合并（= fetch + merge）
```

### 11.6 .gitignore

```
node_modules/
dist/
.env
*.log
.DS_Store
```

---

## 💡 关联面试题

**Q1：Node.js 和浏览器中的 JS 有什么区别？**
- 运行环境不同：浏览器 vs 操作系统
- 顶层对象不同：window vs global
- API 不同：DOM/BOM vs fs/http/path
- 模块系统：ESM vs CommonJS

**Q2：CommonJS 和 ES Module 的区别？**
- CommonJS 运行时加载，输出值的拷贝；ESM 编译时确定，输出值的引用
- CommonJS 同步加载，ESM 异步加载
- CommonJS 用 require/module.exports，ESM 用 import/export

**Q3：Express 中间件的执行机制？**
- 中间件是按注册顺序执行的函数，通过 next() 传递控制权
- 全局中间件 app.use() 对所有请求生效
- 局部中间件只对特定路由生效
- 不调用 next() 请求会卡住
- 错误中间件有 4 个参数 (err, req, res, next)，需放在最后

**Q4：Session 和 JWT 的区别？**
- Session 存在服务端，有状态；JWT 存在客户端，无状态
- Session 扩展性差（需共享 session）；JWT 扩展性好
- Session 适合传统网页；JWT 适合前后端分离和 API

**Q5：npm install 时 --save 和 --save-dev 的区别？**
- `--save`(-S)：写入 dependencies，生产环境需要
- `--save-dev`(-D)：写入 devDependencies，仅开发环境需要
- `npm i --production` 只安装 dependencies

**Q6：Webpack 的核心概念有哪些？Loader 和 Plugin 的区别？**
- 核心：Entry、Output、Loader、Plugin、Mode
- Loader 是文件转换器（如 babel-loader），配置在 module.rules
- Plugin 是扩展插件（如 HtmlWebpackPlugin），配置在 plugins 数组
- Loader 执行从右到左

**Q7：Webpack 和 Vite 的区别？**
- Webpack 打包后启动，启动慢；Vite 基于 ESM 按需加载，启动极快
- Webpack HMR 全量更新；Vite 精确模块更新
- Vite 生产构建基于 Rollup

**Q8：Git 中 merge 和 rebase 的区别？**
- merge 保留分叉历史，生成 merge commit
- rebase 变基，生成线性历史
- rebase 禁止对公共分支使用

**Q9：Git 的工作区、暂存区、版本库是什么关系？**
- 工作区：当前编辑的文件
- 暂存区：git add 后的文件（准备提交）
- 版本库：git commit 后的快照
- 流程：工作区 → add → 暂存区 → commit → 版本库 → push → 远程

**Q10：如何防止 SQL 注入？**
- 使用占位符 `?`，不要直接拼接 SQL 字符串
- 使用 ORM 框架（如 Sequelize、TypeORM）
- 对用户输入进行校验
