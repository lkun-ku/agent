# React 复习

> React 是 Facebook 开源的用于构建用户界面的 JavaScript 库，采用声明式编程和组件化思想，通过虚拟 DOM 实现高效更新。

## 一、React 简介

### 1.1 React 是什么

React 是一个用于构建用户界面的**声明式、组件化** JavaScript 库，核心特点：

- **声明式**：以视图 = f(状态) 的方式描述 UI，数据变化自动更新视图
- **组件化**：将界面拆分为独立可复用的组件，组件内部管理状态与逻辑
- **虚拟 DOM**：通过 Diff 算法对比前后虚拟 DOM，最小化真实 DOM 操作
- **单向数据流**：数据自上而下流动，状态变化可预测
- **JSX**：JavaScript 语法扩展，在 JS 中书写类 HTML 结构

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'

function App() {
  return <h1>Hello React</h1>
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />)
```

### 1.2 React 与 Vue 对比

| 对比项 | React | Vue |
| --- | --- | --- |
| 定位 | UI 库 | 渐进式框架 |
| 视图写法 | JSX（JS 的扩展） | 模板语法（指令） |
| 数据流 | 单向 | 双向（v-model） |
| 状态管理 | useState / useReducer | data + reactive / ref |
| 响应式 | 不可变数据 + setState 触发 | Proxy 自动劫持 |
| 灵活性 | 高（All in JS） | 中（约定大于配置） |
| 学习曲线 | 较陡 | 较平缓 |
| 生态 | Redux、React Router | Pinia、Vue Router |

> 💡 React 强调"不可变数据"，Vue 强调"响应式自动追踪"，这是两者思维上的核心差异

### 1.3 开发环境搭建

**方式一：Vite（推荐，速度快）**

```bash
npm create vite@latest my-react-app -- --template react
cd my-react-app
npm install
npm run dev
```

**方式二：create-react-app 脚手架**

```bash
npx create-react-app my-react-app
cd my-react-app
npm start
```

**项目目录结构（Vite）：**

```
my-react-app/
├── node_modules/
├── public/
│   └── vite.svg
├── src/
│   ├── App.jsx          # 根组件
│   ├── App.css
│   ├── index.jsx        # 入口文件
│   └── index.css        # 全局样式
├── index.html           # HTML 模板
├── package.json
└── vite.config.js
```

---

## 二、JSX 语法

### 2.1 JSX 是什么

JSX 是 JavaScript 的语法扩展，它允许在 JS 中书写类似 HTML 的结构，最终通过 Babel 编译为 `React.createElement()` 调用。

```jsx
// JSX 写法
const el = <h1 className="title">Hello</h1>

// 编译后等价于
const el = React.createElement('h1', { className: 'title' }, 'Hello')
```

### 2.2 JSX 规则

- 必须返回**单根节点**（或使用 Fragment `<>...</>`）
- `class` → `className`，`for` → `htmlFor`
- `style` 接收**对象**，属性名用驼峰
- 表达式用 `{}` 包裹
- 注释写 `{/* 注释 */}`
- 布尔属性、null、undefined 不渲染

```jsx
function App() {
  const name = 'React'
  const isActive = true
  return (
    <>
      {/* 表达式插值 */}
      <h1 className="title">Hello {name}</h1>
      {/* style 接收对象 */}
      <div style={{ color: 'red', fontSize: '16px' }}>样式</div>
      {/* 条件属性 */}
      <button className={isActive ? 'active' : ''}>按钮</button>
      <label htmlFor="user">用户名</label>
    </>
  )
}
```

> ⚠️ JSX 中所有标签必须闭合，如 `<img />`、`<input />`、`<br />`

### 2.3 条件渲染

| 方式 | 适用场景 | 示例 |
| --- | --- | --- |
| `&&` 与运算 | 满足条件才渲染 | `{isLoading && <Loading />}` |
| 三元表达式 | 二选一 | `{isLogin ? <User /> : <Login />}` |
| 提前 return | 复杂分支 / 多条件 | 函数中 `if (...) return <X />` |

```jsx
function List({ list, isLoading }) {
  // 提前 return：加载中
  if (isLoading) return <div>加载中...</div>
  // 提前 return：空列表
  if (list.length === 0) return <div>暂无数据</div>

  return (
    <ul>
      {list.map(item => <li key={item.id}>{item.name}</li>)}
      {/* && 与运算：满足条件才显示徽章 */}
      {list.length > 5 && <span>数据较多</span>}
    </ul>
  )
}
```

### 2.4 列表渲染

使用 `map` 遍历生成元素列表，**必须为每个元素提供稳定的 `key`**。

```jsx
function UserList({ users }) {
  return (
    <ul>
      {users.map(user => (
        <li key={user.id}>
          {user.name} - {user.age}
        </li>
      ))}
    </ul>
  )
}
```

| key 取值 | 是否推荐 | 说明 |
| --- | --- | --- |
| 数据的唯一 id | ✅ 推荐 | 稳定唯一，利于 Diff 复用 |
| 数组 index | ⚠️ 不推荐 | 列表顺序变化时会导致渲染错乱、性能下降 |
| 随机数 | ❌ 禁止 | 每次都变，完全失去 Diff 优化意义 |

> ⚠️ key 的作用：帮助 React 识别哪些元素变化、新增、删除，是 Diff 算法复用节点的关键依据

### 2.5 样式处理

```jsx
// 1. 行内样式
<div style={{ color: 'red', backgroundColor: '#eee' }}>文本</div>

// 2. className + 外部 CSS 文件
import './App.css'
<div className="box">文本</div>

// 3. 动态 className（拼接 / 模板字符串）
<div className={`tab ${isActive ? 'active' : ''}`}>Tab</div>

// 4. CSS Modules（命名 xxx.module.css）
import styles from './App.module.css'
<div className={styles.box}>文本</div>
```

| 方案 | 特点 |
| --- | --- |
| 行内 style | 简单，但难维护、不支持伪类 |
| 普通 CSS 文件 | 直观，但类名全局易冲突 |
| CSS Modules | 局部作用域，类名自动哈希 |
| styled-components | CSS in JS，组件化样式 |
| Tailwind CSS | 原子化 CSS，工具类组合 |

---

## 三、组件

### 3.1 函数组件（推荐）

```jsx
function Welcome(props) {
  return <h1>Hello, {props.name}</h1>
}

// 箭头函数写法
const Welcome = ({ name }) => <h1>Hello, {name}</h1>
```

- 首字母必须**大写**，否则 React 会当作 HTML 标签
- 返回一段 JSX（或 Fragment、null、字符串、数组）
- 自 React 16.8 引入 Hooks 后，函数组件可拥有状态和副作用

### 3.2 类组件（了解）

```jsx
import React, { Component } from 'react'

class Welcome extends Component {
  render() {
    return <h1>Hello, {this.props.name}</h1>
  }
}
```

| 对比项 | 函数组件 | 类组件 |
| --- | --- | --- |
| 语法 | 函数 + Hooks | class 继承 Component |
| 状态 | useState | this.state |
| 生命周期 | useEffect | componentDidMount 等 |
| this | 无 | 有，需绑定 |
| 推荐 | ✅ 新项目首选 | 仅维护旧代码用 |

### 3.3 组件拆分与组合

将复杂界面拆分为独立小组件，通过组合构建完整页面：

```jsx
// 拆分：按钮组件
function Button({ onClick, children }) {
  return <button onClick={onClick}>{children}</button>
}

// 组合：在父组件中使用
function App() {
  return (
    <div>
      <Button onClick={() => alert('保存')}>保存</Button>
      <Button onClick={() => alert('取消')}>取消</Button>
    </div>
  )
}
```

> 💡 组件拆分原则：单一职责、可复用、层级清晰（一般 2~3 层为宜）

---

## 四、Props

### 4.1 Props 基本使用

Props 是父组件传递给子组件的数据，**只读不可修改**。

```jsx
// 子组件：通过参数接收 props
function User({ name, age, hobby }) {
  return (
    <div>
      <p>姓名：{name}</p>
      <p>年龄：{age}</p>
      <p>爱好：{hobby}</p>
    </div>
  )
}

// 父组件：以属性形式传递
function App() {
  return <User name="张三" age={18} hobby="篮球" />
}
```

### 4.2 Props 默认值

```jsx
// 方式一：函数参数默认值（推荐）
function Button({ type = 'default', size = 'md' }) {
  return <button className={`${type} ${size}`}>按钮</button>
}

// 方式二：defaultProps（类组件 / 旧写法）
Button.defaultProps = { type: 'default' }
```

### 4.3 Props 类型校验

```jsx
import PropTypes from 'prop-types'

function User({ name, age, onLogout }) {
  return <div>{name} - {age}</div>
}

User.propTypes = {
  name: PropTypes.string.isRequired,
  age: PropTypes.number,
  onLogout: PropTypes.func
}
```

> 💡 实际项目中推荐使用 **TypeScript** 进行类型约束，比 PropTypes 更严格、有编译期提示

### 4.4 children 属性

`children` 表示组件标签之间的内容，常用于通用容器组件。

```jsx
// 通用卡片组件
function Card({ children }) {
  return <div className="card">{children}</div>
}

// 使用：标签间的内容即 children
function App() {
  return (
    <Card>
      <h2>标题</h2>
      <p>内容</p>
    </Card>
  )
}
```

### 4.5 Props 是只读的

> ⚠️ Props 严禁在子组件中修改！如需修改数据，应通过回调通知父组件，由父组件修改后重新传递

---

## 五、State 与事件（重点）

### 5.1 useState 基本使用

```jsx
import { useState } from 'react'

function Counter() {
  // 声明状态：变量 count，修改方法 setCount，初始值 0
  const [count, setCount] = useState(0)

  return (
    <div>
      <p>当前值：{count}</p>
      <button onClick={() => setCount(count + 1)}>+1</button>
    </div>
  )
}
```

**不可变数据原则：** 状态修改必须返回**新值/新引用**，不能直接修改原状态。

```jsx
const [list, setList] = useState([1, 2, 3])

// ❌ 错误：直接修改原数组
list.push(4)
setList(list)

// ✅ 正确：返回新数组
setList([...list, 4])
```

| 数据类型 | 错误写法 | 正确写法 |
| --- | --- | --- |
| 数组 | `list.push(x)` | `setList([...list, x])` |
| 对象 | `obj.name = 'x'` | `setObj({ ...obj, name: 'x' })` |
| 嵌套对象 | `obj.a.b = 'x'` | `setObj({ ...obj, a: { ...obj.a, b: 'x' } })` |

### 5.2 事件处理

React 事件采用**驼峰命名**，事件处理函数接收**合成事件 SyntheticEvent**。

```jsx
function App() {
  const handleClick = (e) => {
    e.preventDefault()    // 阻止默认行为
    e.stopPropagation()   // 阻止冒泡
    console.log('点击了', e.target)
  }

  return (
    <>
      <button onClick={handleClick}>点击</button>
      <input onChange={(e) => console.log(e.target.value)} />
    </>
  )
}
```

| 原生事件 | React 事件 |
| --- | --- |
| onclick | onClick |
| onchange | onChange |
| oninput | onChange |
| onmouseover | onMouseEnter |

> ⚠️ 合成事件是 React 对原生事件的包装，统一了浏览器差异；React 17+ 事件委托到 root 节点（不再委托到 document）

### 5.3 表单处理

**受控组件：** 表单值由 state 控制，必须配合 onChange（推荐）

```jsx
function Form() {
  const [text, setText] = useState('')
  const [gender, setGender] = useState('male')

  return (
    <form>
      {/* 文本框 */}
      <input value={text} onChange={(e) => setText(e.target.value)} />
      {/* 下拉框 */}
      <select value={gender} onChange={(e) => setGender(e.target.value)}>
        <option value="male">男</option>
        <option value="female">女</option>
      </select>
    </form>
  )
}
```

**非受控组件：** 通过 useRef 直接读取 DOM 值（不推荐，仅特殊场景）

```jsx
import { useRef } from 'react'

function Form() {
  const inputRef = useRef(null)

  const handleSubmit = () => {
    console.log(inputRef.current.value)  // 通过 ref 读取
  }

  return <input ref={inputRef} defaultValue="默认值" />
}
```

| 对比项 | 受控组件 | 非受控组件 |
| --- | --- | --- |
| 数据来源 | state | DOM |
| 数据同步 | 实时（onChange） | 需手动读取 |
| 推荐度 | ✅ 推荐 | ⚠️ 特定场景 |
| 适用 | 表单校验、联动 | 一次性读取、文件上传 |

### 5.4 useState 注意事项

> ⚠️ **异步更新**：连续多次 `setCount(count + 1)` 只会生效一次（基于同一批次的旧值）

```jsx
// ❌ 错误：连续设置基于同一 count，只 +1
const handleAdd = () => {
  setCount(count + 1)
  setCount(count + 1)
  setCount(count + 1)
}

// ✅ 正确：使用函数式更新，基于前一次的值
const handleAdd = () => {
  setCount(prev => prev + 1)
  setCount(prev => prev + 1)
  setCount(prev => prev + 1)
}
```

| 更新方式 | 写法 | 适用场景 |
| --- | --- | --- |
| 直接赋值 | `setCount(count + 1)` | 单次更新，新值与旧值无关 |
| 函数式更新 | `setCount(prev => prev + 1)` | 连续更新、依赖前一次状态 |

### 5.5 状态提升

多个组件需要共享同一状态时，将该状态提升到它们的**共同父组件**中管理。

```jsx
function Parent() {
  const [text, setText] = useState('')
  return (
    <>
      {/* 子A：修改状态 */}
      <Inputer value={text} onChange={setText} />
      {/* 子B：展示状态 */}
      <Shower value={text} />
    </>
  )
}
```

> 💡 状态提升是 React 处理"兄弟通信"的标准方案；跨多层组件时改用 Context

---

## 六、副作用 Hook：useEffect（重点）

### 6.1 基本使用

`useEffect` 用于处理组件中的**副作用**（数据请求、订阅、操作 DOM、定时器等），在渲染完成后执行。

```jsx
import { useEffect, useState } from 'react'

function App() {
  const [count, setCount] = useState(0)

  // 默认每次渲染后都会执行
  useEffect(() => {
    document.title = `当前点击 ${count} 次`
  })

  return <button onClick={() => setCount(count + 1)}>{count}</button>
}
```

### 6.2 依赖数组

| 依赖数组写法 | 执行时机 |
| --- | --- |
| 不传 | 每次渲染后都执行 |
| `[]` 空数组 | 仅在挂载后执行一次 |
| `[dep1, dep2]` | 挂载时 + 依赖变化时执行 |

```jsx
useEffect(() => {
  console.log('每次渲染后执行')
})

useEffect(() => {
  console.log('仅挂载时执行一次')
}, [])

useEffect(() => {
  console.log('count 变化时执行', count)
}, [count])
```

> ⚠️ 依赖数组要写全！如果副作用内部用到了某个 state/props 却未写入依赖，会出现"闭包陷阱"读到旧值。可借助 ESLint 的 `react-hooks/exhaustive-deps` 规则辅助检查

### 6.3 清理副作用

在 effect 中 `return` 一个清理函数，会在组件卸载或下次 effect 执行前调用。

```jsx
useEffect(() => {
  const timer = setInterval(() => {
    console.log('tick')
  }, 1000)

  // 清理函数：清除定时器
  return () => {
    clearInterval(timer)
  }
}, [])
```

> ⚠️ 凡是注册了定时器、事件监听、订阅等，都必须在清理函数中取消，否则会造成内存泄漏

### 6.4 常见使用场景

```jsx
// 1. 数据请求
useEffect(() => {
  fetch('/api/list')
    .then(res => res.json())
    .then(data => setList(data))
}, [])

// 2. 事件监听
useEffect(() => {
  const onScroll = () => console.log(window.scrollY)
  window.addEventListener('scroll', onScroll)
  return () => window.removeEventListener('scroll', onScroll)
}, [])

// 3. 依赖变化时重新请求
useEffect(() => {
  fetch(`/api/list?id=${id}`).then(...)
}, [id])
```

| 场景 | 依赖数组 | 是否需清理 |
| --- | --- | --- |
| 首次数据请求 | `[]` | 视情况 |
| 定时器 | `[]` | ✅ clearInterval |
| 事件监听 | `[]` | ✅ removeEventListener |
| 依赖变化重新请求 | `[id]` | 可选（取消请求） |

---

## 七、其他常用 Hooks

### 7.1 useRef

- 获取 DOM 元素引用
- 保存**不触发重新渲染**的数据（跨渲染保持）

```jsx
import { useRef } from 'react'

function App() {
  const inputRef = useRef(null)
  const timerRef = useRef(null)  // 保存数据，不触发渲染

  const focusInput = () => inputRef.current.focus()

  return <input ref={inputRef} />
}
```

| 对比项 | useState | useRef |
| --- | --- | --- |
| 修改是否触发渲染 | ✅ 触发 | ❌ 不触发 |
| 跨渲染保持 | ✅ | ✅ |
| 访问方式 | 变量直接读 | `.current` |
| 适用场景 | 需要显示的数据 | DOM 引用、定时器 ID、缓存 |

### 7.2 useMemo

缓存**计算结果**，依赖不变时返回缓存值，避免重复计算。

```jsx
import { useMemo, useState } from 'react'

function App({ list }) {
  const [keyword, setKeyword] = useState('')

  // 仅在 list 变化时重新计算，避免每次渲染都排序
  const sorted = useMemo(() => {
    return [...list].sort((a, b) => a - b)
  }, [list])

  return <input value={keyword} onChange={e => setKeyword(e.target.value)} />
}
```

### 7.3 useCallback

缓存**函数引用**，依赖不变时返回同一函数，常配合 `React.memo` 优化子组件。

```jsx
import { useCallback, useState } from 'react'

const Parent = () => {
  const [count, setCount] = useState(0)
  const [text, setText] = useState('')

  // 缓存函数：count 变化时 text 相关子组件不重新渲染
  const handleClick = useCallback(() => {
    console.log('点击')
  }, [])

  return (
    <>
      <input value={text} onChange={e => setText(e.target.value)} />
      <Child onClick={handleClick} />
    </>
  )
}
```

| Hook | 缓存对象 | 触发重新缓存的条件 |
| --- | --- | --- |
| useMemo | 计算结果（值） | 依赖变化 |
| useCallback | 函数引用 | 依赖变化 |

### 7.4 useContext

跨组件传递数据，避免层层 props 传递。

```jsx
import { createContext, useContext } from 'react'

// 1. 创建 Context
const ThemeContext = createContext('light')

// 2. 父组件通过 Provider 提供数据
function App() {
  return (
    <ThemeContext.Provider value="dark">
      <Child />
    </ThemeContext.Provider>
  )
}

// 3. 后代组件通过 useContext 消费
function Child() {
  const theme = useContext(ThemeContext)
  return <div>当前主题：{theme}</div>
}
```

### 7.5 useReducer

用于管理**复杂状态**（多字段、状态间有依赖），是 useState 的替代方案。

```jsx
import { useReducer } from 'react'

// 1. 定义 reducer
function reducer(state, action) {
  switch (action.type) {
    case 'increment': return { count: state.count + 1 }
    case 'decrement': return { count: state.count - 1 }
    case 'reset':     return { count: 0 }
    default: return state
  }
}

function Counter() {
  // 2. useReducer 接收 reducer 和初始状态
  const [state, dispatch] = useReducer(reducer, { count: 0 })

  return (
    <div>
      <p>{state.count}</p>
      <button onClick={() => dispatch({ type: 'increment' })}>+1</button>
      <button onClick={() => dispatch({ type: 'reset' })}>重置</button>
    </div>
  )
}
```

| 对比项 | useState | useReducer |
| --- | --- | --- |
| 状态复杂度 | 简单状态 | 复杂/关联状态 |
| 更新方式 | 直接 set 新值 | dispatch action |
| 适用场景 | 单值、对象少量字段 | 多字段、状态机、表单 |

### 7.6 自定义 Hook

以 `use` 开头的函数，用于**封装可复用的有状态逻辑**。

```jsx
import { useState, useEffect } from 'react'

// 自定义 Hook：窗口尺寸监听
function useWindowSize() {
  const [size, setSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight
  })

  useEffect(() => {
    const onResize = () => setSize({
      width: window.innerWidth,
      height: window.innerHeight
    })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  return size
}

// 使用
function App() {
  const { width, height } = useWindowSize()
  return <p>窗口：{width} x {height}</p>
}
```

> 💡 自定义 Hook 的本质：把组件中用到的多个内置 Hook 组合起来，让逻辑在不同组件间复用

---

## 八、组件通信

### 8.1 父传子：props

```jsx
function Child({ msg }) {
  return <p>{msg}</p>
}
function Parent() {
  return <Child msg="来自父组件" />
}
```

### 8.2 子传父：回调函数 props

父组件传入一个函数，子组件调用该函数并传参。

```jsx
function Child({ onSend }) {
  return <button onClick={() => onSend('子组件数据')}>发送</button>
}
function Parent() {
  const handleSend = (data) => console.log('收到：', data)
  return <Child onSend={handleSend} />
}
```

### 8.3 兄弟通信：状态提升

将共享状态放到共同父组件，通过 props + 回调传递。

```jsx
function Parent() {
  const [count, setCount] = useState(0)
  return (
    <>
      <BroA count={count} />
      <BroB onAdd={() => setCount(count + 1)} />
    </>
  )
}
```

### 8.4 跨层级：Context

```jsx
// 祖先提供 Provider，任意后代 useContext 消费
const Ctx = createContext()
;<Ctx.Provider value={{ user: '张三' }}>
  <深层组件 />
</Ctx.Provider>
```

### 8.5 任意通信：状态管理工具

| 方案 | 通信范围 | 适用场景 |
| --- | --- | --- |
| props / 回调 | 父子 | 简单组件 |
| 状态提升 | 兄弟 | 2~3 个组件共享 |
| Context | 跨层级 | 主题、用户信息等全局数据 |
| Redux | 任意 | 大型应用、复杂状态 |
| Zustand | 任意 | 轻量、API 简洁 |

> ⚠️ Context 的 value 变化会让所有消费该 Context 的组件重新渲染，不适合高频变化的数据（如购物车数量）

---

## 九、React Router

### 9.1 安装与基本使用

```bash
npm install react-router-dom
```

### 9.2 路由配置

```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import About from './pages/About'
import NotFound from './pages/NotFound'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  )
}
```

| 路由模式 | URL 形式 | 说明 |
| --- | --- | --- |
| BrowserRouter | `/about` | 需服务器配置重定向到 index.html |
| HashRouter | `/#/about` | 兼容性好，无需服务器配置 |

### 9.3 路由跳转

```jsx
import { Link, NavLink, useNavigate } from 'react-router-dom'

function Menu() {
  const navigate = useNavigate()

  return (
    <nav>
      {/* Link：普通跳转 */}
      <Link to="/about">关于</Link>
      {/* NavLink：激活时自动加 active 类 */}
      <NavLink to="/home">首页</NavLink>
      {/* 编程式导航 */}
      <button onClick={() => navigate('/about')}>跳转</button>
      <button onClick={() => navigate(-1)}>返回</button>
    </nav>
  )
}
```

### 9.4 动态路由参数

```jsx
// 路由配置
<Route path="/user/:id" element={<User />} />

// 组件中获取
import { useParams } from 'react-router-dom'
function User() {
  const { id } = useParams()
  return <p>用户 ID：{id}</p>
}
```

### 9.5 查询参数

```jsx
// 访问 /search?keyword=react&page=1
import { useSearchParams } from 'react-router-dom'
function Search() {
  const [params, setParams] = useSearchParams()
  const keyword = params.get('keyword')
  const page = params.get('page')
  return <p>{keyword} - 第{page}页</p>
}
```

### 9.6 嵌套路由

```jsx
// 父路由用 <Outlet /> 渲染子路由
function Layout() {
  return (
    <div>
      <h1>头部</h1>
      <Outlet />
    </div>
  )
}

// 配置
<Routes>
  <Route path="/" element={<Layout />}>
    <Route index element={<Home />} />       {/* 默认子路由 */}
    <Route path="about" element={<About />} />
  </Route>
</Routes>
```

### 9.7 路由守卫

```jsx
function AuthRoute({ children }) {
  const isLogin = localStorage.getItem('token')
  if (!isLogin) return <Navigate to="/login" replace />
  return children
}

// 使用
<Route path="/profile" element={
  <AuthRoute><Profile /></AuthRoute>
} />
```

---

## 十、状态管理 Redux

### 10.1 Redux 核心概念

| 概念 | 说明 |
| --- | --- |
| store | 存储整个应用状态的对象 |
| action | 描述"做什么"的纯对象，必须有 `type` 字段 |
| reducer | 纯函数，根据 action 计算并返回新 state |
| dispatch | 派发 action 触发状态更新 |
| 单向数据流 | UI → dispatch(action) → reducer → 新 state → UI |

```jsx
// 1. 定义 reducer
function counterReducer(state = { count: 0 }, action) {
  switch (action.type) {
    case 'ADD': return { count: state.count + 1 }
    case 'SUB': return { count: state.count - 1 }
    default: return state
  }
}

// 2. 创建 store
import { createStore } from 'redux'
const store = createStore(counterReducer)

// 3. 派发 action
store.dispatch({ type: 'ADD' })
console.log(store.getState())
```

> ⚠️ reducer 必须是**纯函数**：不能修改原 state、不能有副作用、相同输入必须相同输出

### 10.2 Redux Toolkit（推荐）

Redux Toolkit（RTK）是官方推荐的写法，简化了 Redux 的样板代码。

```jsx
import { configureStore, createSlice } from '@reduxjs/toolkit'

// 1. 创建 slice（自动生成 action 和 reducer）
const counterSlice = createSlice({
  name: 'counter',
  initialState: { count: 0 },
  reducers: {
    // 这里的"可变"写法由 Immer 处理，实际返回新对象
    add(state) { state.count += 1 },
    sub(state) { state.count -= 1 },
    addBy(state, action) { state.count += action.payload }
  }
})

export const { add, sub, addBy } = counterSlice.actions

// 2. 配置 store
const store = configureStore({
  reducer: { counter: counterSlice.reducer }
})
```

**在组件中使用：**

```jsx
import { useSelector, useDispatch } from 'react-redux'
import { add, addBy } from './store/counterSlice'

function Counter() {
  const count = useSelector(state => state.counter.count)
  const dispatch = useDispatch()

  return (
    <div>
      <p>{count}</p>
      <button onClick={() => dispatch(add())}>+1</button>
      <button onClick={() => dispatch(addBy(5))}>+5</button>
    </div>
  )
}
```

### 10.3 异步操作

使用 `createAsyncThunk` 处理异步请求。

```jsx
import { createAsyncThunk } from '@reduxjs/toolkit'

export const fetchList = createAsyncThunk('list/fetch', async () => {
  const res = await fetch('/api/list')
  return res.json()
})

const listSlice = createSlice({
  name: 'list',
  initialState: { data: [], status: 'idle' },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchList.pending, (state) => { state.status = 'loading' })
      .addCase(fetchList.fulfilled, (state, action) => {
        state.status = 'success'
        state.data = action.payload
      })
      .addCase(fetchList.rejected, (state) => { state.status = 'error' })
  }
})
```

### 10.4 React-Redux

```jsx
import { Provider } from 'react-redux'

// 在根组件用 Provider 提供 store
function App() {
  return (
    <Provider store={store}>
      <Root />
    </Provider>
  )
}
```

| 方式 | 写法 | 说明 |
| --- | --- | --- |
| connect（旧） | `connect(mapState, mapDispatch)(Comp)` | 类组件 / 老项目 |
| hooks（新） | useSelector / useDispatch | 推荐，函数组件 |

---

## 十一、性能优化

### 11.1 React.memo

对函数组件进行**记忆化**，props 不变时跳过重新渲染。

```jsx
const Child = React.memo(function Child({ count }) {
  console.log('子组件渲染')
  return <p>{count}</p>
})
```

### 11.2 useMemo / useCallback

| 优化手段 | 作用 | 配合使用 |
| --- | --- | --- |
| useMemo | 缓存计算结果 | 避免昂贵计算重复执行 |
| useCallback | 缓存函数引用 | 配合 React.memo 防止子组件无意义重渲染 |
| React.memo | 缓存组件 | props 不变跳过渲染 |

```jsx
const Parent = () => {
  const [text, setText] = useState('')
  const [count, setCount] = useState(0)

  // 缓存函数，避免每次都新建导致 Child 重渲染
  const handleClick = useCallback(() => setCount(c => c + 1), [])

  return (
    <>
      <input value={text} onChange={e => setText(e.target.value)} />
      <MemoChild onClick={handleClick} count={count} />
    </>
  )
}
```

### 11.3 虚拟列表

长列表只渲染可视区域内的元素，使用 `react-window` 或 `react-virtualized`。

```jsx
import { FixedSizeList } from 'react-window'

const Row = ({ index, style }) => (
  <div style={style}>第 {index} 行</div>
)

function BigList({ data }) {
  return (
    <FixedSizeList
      height={400}
      width={300}
      itemSize={40}
      itemCount={data.length}
    >
      {Row}
    </FixedSizeList>
  )
}
```

### 11.4 懒加载

使用 `React.lazy` + `Suspense` 实现路由/组件按需加载，减小首屏体积。

```jsx
import { lazy, Suspense } from 'react'

const About = lazy(() => import('./pages/About'))

function App() {
  return (
    <Suspense fallback={<div>加载中...</div>}>
      <About />
    </Suspense>
  )
}
```

### 11.5 key 的正确使用

> ⚠️ 列表渲染必须用稳定唯一的 key（数据 id），不要用 index；key 错误会导致状态错乱、性能下降

| 优化手段 | 适用场景 |
| --- | --- |
| React.memo | 子组件 props 不变却频繁重渲染 |
| useMemo | 昂贵计算每次都重复执行 |
| useCallback | 传递给子组件的函数引用变化 |
| 虚拟列表 | 渲染上千条数据 |
| 懒加载 | 路由组件 / 大型组件 |
| 合理 key | 列表增删改 |

---

## 💡 关联面试题

**Q1：React 和 Vue 的区别？**
- 写法：React 用 JSX（All in JS），Vue 用模板语法（指令）
- 响应式：React 需手动 setState（不可变数据），Vue 用 Proxy 自动追踪
- 数据流：React 单向，Vue 支持 v-model 双向
- 灵活性：React 更高，Vue 约定大于配置
- 学习曲线：React 较陡，Vue 较平缓

**Q2：虚拟 DOM 是什么？Diff 算法的策略？**
- 虚拟 DOM 是用 JS 对象描述真实 DOM 的树结构，状态变化先生成新虚拟 DOM，与旧虚拟 DOM 对比（Diff），最后只更新差异部分到真实 DOM
- Diff 策略：① 同层比较 ② 类型不同直接替换整个子树 ③ 列表通过 key 复用节点，减少创建销毁

**Q3：useState 和 useRef 的区别？**
- useState 修改会触发重新渲染，useRef 修改不会
- useState 用于显示数据，useRef 用于 DOM 引用、保存不触发渲染的数据（如定时器 ID）
- useState 通过解构的值访问，useRef 通过 `.current` 访问

**Q4：useEffect 的依赖数组有什么作用？**
- 不传：每次渲染后都执行
- `[]`：仅挂载后执行一次
- `[dep]`：挂载时 + 依赖变化时执行
- 用于控制副作用执行时机；依赖要写全否则会闭包陷阱读到旧值；return 清理函数避免内存泄漏

**Q5：useMemo 和 useCallback 的区别？什么时候用？**
- useMemo 缓存**值**，useCallback 缓存**函数引用**
- 用于优化：useMemo 避免昂贵计算重复执行；useCallback 配合 React.memo 防止子组件因函数引用变化而无意义重渲染
- 滥用反而增加开销，仅在确有性能问题时使用

**Q6：受控组件和非受控组件的区别？**
- 受控组件：表单值由 state 控制，配合 onChange 实时同步，推荐使用
- 非受控组件：表单值由 DOM 管理，通过 useRef 读取，适合一次性读取或文件上传

**Q7：React 组件通信有哪些方式？**
- 父传子：props
- 子传父：回调函数 props
- 兄弟：状态提升
- 跨层级：Context
- 任意：Redux / Zustand 等状态管理工具

**Q8：Redux 的工作流程？Redux Toolkit 的优势？**
- 工作流程：UI dispatch(action) → reducer 根据 action 计算新 state → store 更新 → 触发订阅的 UI 重新渲染
- RTK 优势：内置 Immer 支持可变写法、自动生成 action creators、减少样板代码、内置 configureStore 简化配置

**Q9：React 性能优化有哪些手段？**
- React.memo 记忆化组件
- useMemo / useCallback 缓存值与函数
- 虚拟列表（react-window）渲染大数据
- React.lazy + Suspense 懒加载
- 列表使用稳定唯一的 key
- 合理拆分组件，减小重渲染范围

**Q10：自定义 Hook 的作用？举例说明？**
- 作用：将组件中可复用的有状态逻辑（涉及 useState/useEffect 等）封装成函数，在不同组件间复用
- 举例：`useWindowSize`（监听窗口尺寸）、`useFetch`（封装请求逻辑）、`useLocalStorage`（本地存储读写）
