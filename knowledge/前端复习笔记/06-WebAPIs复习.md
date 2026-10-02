# Web APIs 复习

> Web APIs 是浏览器提供的接口，用于操作网页（DOM）和浏览器窗口（BOM），以及处理用户交互事件。本文系统梳理 DOM 操作、节点操作、事件机制、BOM、本地存储、日期对象、JSON、正则表达式等核心知识点。

## 一、DOM 基础

### 1.1 DOM 树与节点

DOM（Document Object Model）将 HTML 文档解析为树形结构，文档中所有内容都是节点。

| 节点类型 | 说明 | 示例 |
| --- | --- | --- |
| document 节点 | 整个文档 | `document` |
| element 节点 | HTML 标签 | `<div>`、`<p>` |
| text 节点 | 标签内的文本 | `Hello` |
| comment 节点 | 注释 | `<!-- 注释 -->` |
| attribute 节点 | 标签属性 | `class="box"` |

```javascript
// DOM 树结构示例
// document
//   └── html
//        ├── head
//        │    ├── title
//        │    └── meta
//        └── body
//             ├── div
//             └── p
```

### 1.2 获取元素

```javascript
// 1. 通过 ID 获取（返回单个元素）
const box = document.getElementById('box')

// 2. 通过标签名获取（返回伪数组 HTMLCollection）
const lis = document.getElementsByTagName('li')

// 3. 通过类名获取（返回伪数组 HTMLCollection）
const items = document.getElementsByClassName('item')

// 4. querySelector（返回第一个匹配的元素，推荐）
const firstBox = document.querySelector('#box')
const firstItem = document.querySelector('.item')
const firstLi = document.querySelector('ul li')

// 5. querySelectorAll（返回所有匹配的元素 NodeList，推荐）
const allItems = document.querySelectorAll('.item')
allItems.forEach(item => console.log(item))
```

| 方法 | 返回值 | 是否实时 | 推荐 |
| --- | --- | --- | --- |
| `getElementById` | 单个 Element | 是 | ✅ |
| `getElementsByTagName` | HTMLCollection | 是（动态） | - |
| `getElementsByClassName` | HTMLCollection | 是（动态） | - |
| `querySelector` | 第一个 Element / null | 否（静态） | ✅ |
| `querySelectorAll` | NodeList | 否（静态） | ✅ |

⚠️ **易错点**：`querySelectorAll` 返回的是静态 NodeList，可用 `forEach` 遍历；`getElementsByTagName` 返回的是动态 HTMLCollection，不能直接用 `forEach`，需用 `Array.from()` 转换或 `for` 循环。

### 1.3 修改元素内容

```javascript
const box = document.querySelector('.box')

// innerHTML：解析 HTML 标签
box.innerHTML = '<strong>加粗内容</strong>'

// innerText：纯文本，不解析标签，受样式影响（隐藏元素读取不到）
box.innerText = '<strong>普通文本</strong>'  // 显示原始字符串

// textContent：纯文本，包含隐藏元素文本（推荐）
box.textContent = '纯文本内容'
```

| 属性 | 是否解析 HTML | 是否包含隐藏元素文本 | 性能 |
| --- | --- | --- | --- |
| `innerHTML` | ✅ 解析 | ✅ | 较慢（需解析 HTML） |
| `innerText` | ❌ 不解析 | ❌ | 最慢（需计算样式） |
| `textContent` | ❌ 不解析 | ✅ | 最快 |

⚠️ **易错点**：使用 `innerHTML` 插入用户输入内容会有 XSS 安全风险，应优先使用 `textContent`。

### 1.4 修改元素属性

```javascript
const img = document.querySelector('img')

// 1. 普通属性：直接操作
img.src = './new.jpg'
img.title = '新图片'
img.alt = '图片描述'

// 2. 自定义属性：data-*（推荐使用 dataset）
const div = document.querySelector('div')
div.setAttribute('data-id', '100')   // 设置
div.getAttribute('data-id')           // 获取：'100'
div.removeAttribute('data-id')         // 移除

// dataset 操作 data-* 属性
div.dataset.id = '100'        // 对应 data-id
div.dataset.userName = 'tom'  // 对应 data-user-name（驼峰转连字符）

// 3. class 属性操作：classList（推荐）
const box = document.querySelector('.box')
box.classList.add('active')       // 添加类
box.classList.remove('active')   // 移除类
box.classList.toggle('active')   // 切换类（有则删，无则加）
box.classList.contains('active') // 判断是否包含某类，返回 boolean
```

⚠️ **易错点**：`dataset` 访问 `data-user-name` 时需写成驼峰 `dataset.userName`（连字符转驼峰）。

### 1.5 修改元素样式

```javascript
const box = document.querySelector('.box')

// 1. style 属性：行内样式，驼峰命名（推荐用于少量动态样式）
box.style.backgroundColor = 'red'   // background-color → backgroundColor
box.style.fontSize = '20px'        // font-size → fontSize
box.style.cssText = 'color: red; font-size: 20px;'  // 批量设置（会覆盖原有行内样式）

// 2. className：覆盖原有 class（慎用）
box.className = 'newClass'  // 会覆盖原有所有 class

// 3. classList：增量操作（推荐）
box.classList.add('active')
box.classList.remove('hidden')
```

| 方式 | 适用场景 | 注意事项 |
| --- | --- | --- |
| `style` | 少量动态样式 | 属性名需驼峰化 |
| `className` | 整体替换 class | ⚠️ 会覆盖原有 class |
| `classList` | 增量操作 class | 推荐，不影响其他 class |

⚠️ **易错点**：CSS 属性名在 JS 中需用驼峰命名（`background-color` → `backgroundColor`），`-` 是减号运算符。

---

## 二、DOM 节点操作

### 2.1 节点关系

```javascript
const ul = document.querySelector('ul')
const li = document.querySelector('li')

// 父节点（推荐 element 系列，不含文本节点）
li.parentNode              // 父节点
li.parentElement           // 父元素节点

// 子节点
ul.childNodes             // 所有子节点（含文本、注释节点）
ul.children               // 所有子元素节点（推荐）
ul.firstChild             // 第一个子节点（可能是文本节点）
ul.firstElementChild      // 第一个子元素节点（推荐）
ul.lastChild              // 最后一个子节点
ul.lastElementChild       // 最后一个子元素节点

// 兄弟节点
li.previousSibling        // 前一个兄弟节点（可能是文本节点）
li.previousElementSibling// 前一个兄弟元素节点（推荐）
li.nextSibling            // 后一个兄弟节点
li.nextElementSibling     // 后一个兄弟元素节点（推荐）
```

⚠️ **易错点**：`childNodes` / `firstChild` 等会包含文本节点（包括换行符），开发中推荐使用 `children` / `firstElementChild` 等 `element` 系列属性。

### 2.2 创建节点

```javascript
// 创建元素节点
const div = document.createElement('div')
div.className = 'box'
div.textContent = '新建的 div'

// 创建文本节点（较少使用）
const text = document.createTextNode('文本内容')
```

### 2.3 插入节点

```javascript
const ul = document.querySelector('ul')
const li = document.createElement('li')
li.textContent = '新列表项'

// 1. appendChild：追加到子节点列表末尾
ul.appendChild(li)

// 2. insertBefore：在指定子节点前插入
const firstLi = ul.firstElementChild
ul.insertBefore(li, firstLi)  // 新节点插到第一个 li 前面
```

### 2.4 删除节点

```javascript
const ul = document.querySelector('ul')
const li = ul.firstElementChild

// 方式一：父节点调用 removeChild（推荐，兼容性好）
ul.removeChild(li)

// 方式二：节点自身调用 remove（ newer API）
li.remove()
```

### 2.5 克隆节点

```javascript
const ul = document.querySelector('ul')

// cloneNode(false)（默认）：浅拷贝，只复制标签本身，不复制子节点
const shallowClone = ul.cloneNode(false)

// cloneNode(true)：深拷贝，复制标签及其所有子节点（推荐）
const deepClone = ul.cloneNode(true)
document.body.appendChild(deepClone)
```

⚠️ **易错点**：`cloneNode` 默认参数是 `false`（浅拷贝），深拷贝需显式传 `true`；克隆不会复制事件监听器，只复制行内属性。

---

## 三、事件机制（重点）

### 3.1 事件注册

```javascript
const btn = document.querySelector('button')

// 1. 传统方式：on + 事件名（同一元素同一事件只能绑定一个，后写的覆盖前面的）
btn.onclick = function () {
  console.log('点击1')
}
btn.onclick = function () {
  console.log('点击2')  // 只执行这个
}

// 2. 事件监听：addEventListener（可绑定多个，推荐）
function handleClick() {
  console.log('监听点击')
}
btn.addEventListener('click', handleClick)

// 移除监听（必须传同一个函数引用）
btn.removeEventListener('click', handleClick)

// 3. 支持事件捕获/冒泡（第三个参数）
btn.addEventListener('click', fn, false)  // 冒泡（默认）
btn.addEventListener('click', fn, true)   // 捕获
```

| 对比项 | `onclick` | `addEventListener` |
| --- | --- | --- |
| 绑定数量 | 同一事件只能绑一个 | 可绑多个，依次执行 |
| 移除方式 | `btn.onclick = null` | `removeEventListener` |
| 事件流控制 | 不支持 | 支持（第三参数） |
| 兼容性 | 全兼容 | IE9+（IE 用 attachEvent） |
| 推荐 | ❌ | ✅ |

⚠️ **易错点**：`removeEventListener` 移除时传入的回调必须与 `addEventListener` 是**同一个函数引用**（匿名函数无法移除）。

### 3.2 事件类型

| 类别 | 事件 | 触发时机 |
| --- | --- | --- |
| 鼠标事件 | `click` | 单击 |
|  | `dblclick` | 双击 |
|  | `mouseenter` | 鼠标进入（不冒泡，推荐） |
|  | `mouseleave` | 鼠标离开（不冒泡，推荐） |
|  | `mouseover` | 鼠标进入（会冒泡） |
|  | `mouseout` | 鼠标离开（会冒泡） |
|  | `mousemove` | 鼠标移动 |
| 键盘事件 | `keydown` | 按键按下 |
|  | `keyup` | 按键抬起 |
| 表单事件 | `input` | 输入内容变化（实时） |
|  | `change` | 内容变化且失焦时 |
|  | `focus` | 获得焦点 |
|  | `blur` | 失去焦点 |
|  | `submit` | 表单提交 |
| 滚动事件 | `scroll` | 滚动条滚动 |
| 窗口事件 | `resize` | 窗口大小变化 |
|  | `load` | 页面所有资源加载完成 |
|  | `DOMContentLoaded` | DOM 解析完成（不需等图片） |

```javascript
// 区别 input 与 change
const input = document.querySelector('input')
input.addEventListener('input', e => console.log('实时变化:', e.target.value))
input.addEventListener('change', e => console.log('失焦且变化:', e.target.value))

// 区别 mouseenter 与 mouseover
// mouseenter：进入元素本身触发，不会冒泡，进入子元素不重复触发
// mouseover：进入元素或其子元素都触发，会冒泡
```

⚠️ **易错点**：`load` 事件需等待所有资源（图片、CSS 等）加载完成，`DOMContentLoaded` 只需 DOM 解析完成，所以后者先触发，推荐将 JS 逻辑放在 `DOMContentLoaded` 中。

### 3.3 事件对象 Event

事件触发时，回调函数会自动接收一个事件对象 `event`。

```javascript
const ul = document.querySelector('ul')
ul.addEventListener('click', function (e) {
  // e.target：真正触发事件的元素（如点击的 li）
  console.log('target:', e.target)

  // e.currentTarget：绑定事件的元素（这里是 ul）
  console.log('currentTarget:', e.currentTarget)

  // 事件类型
  console.log('type:', e.type)  // 'click'

  // 阻止默认行为（如 a 标签跳转、表单提交）
  e.preventDefault()

  // 阻止事件冒泡
  e.stopPropagation()
})
```

**鼠标坐标：**

| 属性 | 参照系 | 说明 |
| --- | --- | --- |
| `e.clientX` / `e.clientY` | 浏览器可视区域 | 不随滚动条变化 |
| `e.pageX` / `e.pageY` | 整个文档页面 | 随滚动条变化 |
| `e.offsetX` / `e.offsetY` | 事件目标元素自身 | 相对元素左上角 |

**键盘属性：**

```javascript
document.addEventListener('keydown', function (e) {
  console.log(e.key)      // 按键的值，如 'a'、'Enter'、'ArrowUp'（推荐）
  console.log(e.code)    // 物理按键代码，如 'KeyA'、'Enter'
  console.log(e.keyCode) // ASCII 码（已废弃，不推荐）
})
```

⚠️ **易错点**：`e.target` 是触发事件的元素，`e.currentTarget` 是绑定监听器的元素，两者在事件委托场景下不同。

### 3.4 事件流

事件流描述事件从触发到响应的传播过程，分三个阶段：**捕获阶段 → 目标阶段 → 冒泡阶段**。

```
事件流（点击 li）：
  捕获阶段：document → html → body → ul → li（由外到内）
  目标阶段：li（事件源）
  冒泡阶段：li → ul → body → html → document（由内到外，默认触发）
```

```javascript
const father = document.querySelector('.father')
const son = document.querySelector('.son')

// 第三个参数：false（默认）冒泡阶段触发，true 捕获阶段触发
father.addEventListener('click', () => {
  console.log('father 捕获')
}, true)

father.addEventListener('click', () => {
  console.log('father 冒泡')
}, false)

son.addEventListener('click', () => {
  console.log('son 冒泡')
}, false)

// 点击 son 时输出顺序：
// father 捕获 → son 冒泡 → father 冒泡
```

| 阶段 | 方向 | 触发条件 |
| --- | --- | --- |
| 捕获阶段 | 由外到内 | `addEventListener` 第三参数为 `true` |
| 目标阶段 | 事件源本身 | 始终触发 |
| 冒泡阶段 | 由内到外 | `addEventListener` 第三参数为 `false`（默认） |

⚠️ **易错点**：事件目标（如点击的 `son`）上注册的事件，无论第三参数是 `true` 还是 `false`，都会在目标阶段触发，顺序按注册顺序执行。

### 3.5 事件委托

**原理**：利用事件冒泡，将多个子元素的事件统一绑定到父元素上，通过 `e.target` 判断真正触发的子元素。

```javascript
// 传统做法：每个 li 都绑定事件（性能差，动态添加的 li 无事件）
const lis = document.querySelectorAll('li')
lis.forEach(li => {
  li.addEventListener('click', function () {
    console.log(this.textContent)
  })
})

// 事件委托：只绑定到父元素 ul（推荐）
const ul = document.querySelector('ul')
ul.addEventListener('click', function (e) {
  if (e.target.tagName === 'LI') {  // 判断点击的是否是 li
    e.target.style.color = 'red'
    console.log(e.target.textContent)
  }
})
```

**优点：**
1. 减少事件绑定数量，提升性能
2. 动态添加的子元素也能触发事件（无需重新绑定）
3. 方便统一管理事件

💡 **应用场景**：列表项点击、表格行操作、动态生成的菜单等。

---

## 四、BOM 浏览器对象模型

### 4.1 window 对象

`window` 是浏览器的全局对象，所有全局变量和函数都是它的属性/方法。

```javascript
// 全局变量成为 window 的属性
var a = 10
console.log(window.a)  // 10（let/const 声明的不会）

// 全局函数成为 window 的方法
function fn() {}
console.log(window.fn)  // function

// 常用全局方法（window. 可省略）
window.alert('提示')        // 警告框
window.confirm('确认？')    // 确认框，返回 boolean
window.prompt('请输入')     // 输入框，返回 string
```

### 4.2 定时器

```javascript
// 1. setTimeout：延时执行一次
const timer1 = setTimeout(() => {
  console.log('2 秒后执行')
}, 2000)
clearTimeout(timer1)  // 取消

// 2. setInterval：重复执行
const timer2 = setInterval(() => {
  console.log('每 1 秒执行一次')
}, 1000)
clearInterval(timer2)  // 取消

// 3. requestAnimationFrame：与屏幕刷新同步（推荐用于动画）
let count = 0
function animate() {
  count++
  console.log('动画帧:', count)
  if (count < 60) {
    requestAnimationFrame(animate)
  }
}
requestAnimationFrame(animate)
```

| 方法 | 执行次数 | 适用场景 | 注意事项 |
| --- | --- | --- | --- |
| `setTimeout` | 1 次 | 延时任务 | 需保存 id 用 `clearTimeout` 清除 |
| `setInterval` | 重复 | 倒计时、轮询 | ⚠️ 不准时，会受主线程阻塞影响 |
| `requestAnimationFrame` | 重复 | 动画 | 跟随屏幕刷新率（60fps），隐藏标签页自动暂停 |

⚠️ **易错点**：`setInterval` 不保证准时执行，因为 JS 是单线程，如果主线程有耗时任务会延迟触发。做精确倒计时推荐用 `setTimeout` 递归 + `Date` 校准时间。

```javascript
// 倒计时正确做法：用时间戳校准
function countdown(seconds) {
  const startTime = Date.now()
  const endTime = startTime + seconds * 1000

  function update() {
    const remaining = endTime - Date.now()
    if (remaining <= 0) {
      console.log('倒计时结束')
      return
    }
    console.log('剩余:', Math.ceil(remaining / 1000), '秒')
    setTimeout(update, 1000)
  }
  update()
}
countdown(10)
```

### 4.3 location 对象

`location` 提供当前 URL 的信息，并可进行页面跳转。

```javascript
// 假设 URL：https://www.example.com:8080/page?id=1&name=tom#section
console.log(location.href)      // 完整 URL
console.log(location.protocol) // 'https:'
console.log(location.host)     // 'www.example.com:8080'
console.log(location.hostname) // 'www.example.com'
console.log(location.port)     // '8080'
console.log(location.pathname) // '/page'
console.log(location.search)   // '?id=1&name=tom'（查询参数）
console.log(location.hash)     // '#section'（锚点）

// 方法
location.href = 'https://www.baidu.com'  // 跳转（可后退）
location.assign('https://www.baidu.com') // 跳转（可后退，等价于上）
location.replace('https://www.baidu.com')// 跳转（不可后退，替换历史记录）
location.reload()                        // 刷新页面（强制刷新传 true）
```

| 属性/方法 | 说明 |
| --- | --- |
| `location.href` | 获取 / 设置完整 URL |
| `location.search` | 查询参数（`?key=value`） |
| `location.hash` | 锚点（`#xxx`），常用于 SPA 路由 |
| `location.reload()` | 刷新页面 |
| `location.assign()` | 跳转，保留历史记录 |
| `location.replace()` | 跳转，替换历史记录（不可后退） |

### 4.4 navigator 对象

```javascript
// 获取浏览器信息
console.log(navigator.userAgent)  // 浏览器标识字符串
console.log(navigator.language)   // 浏览器语言
console.log(navigator.platform)   // 操作系统平台

// 判断设备类型（移动端 / PC 端）
const isMobile = /Mobile|Android|iPhone/i.test(navigator.userAgent)
console.log(isMobile ? '移动端' : 'PC 端')
```

### 4.5 history 对象

```javascript
history.back()     // 后退
history.forward()  // 前进
history.go(-1)     // 后退一页（正数前进）
history.go(1)      // 前进一页

// HTML5 新增：SPA 路由相关
history.pushState({ page: 1 }, '', '/page1')  // 添加历史记录（不刷新页面）
history.replaceState({ page: 1 }, '', '/page1') // 替换当前记录

// 监听历史记录变化（pushState/replaceState 不触发，需配合 popstate）
window.addEventListener('popstate', function (e) {
  console.log('路由变化', e.state)
})
```

### 4.6 screen 对象

```javascript
console.log(screen.width)    // 屏幕宽度
console.log(screen.height)   // 屏幕高度
console.log(screen.availWidth)  // 可用宽度（除任务栏）
console.log(screen.availHeight) // 可用高度
```

---

## 五、本地存储

### 5.1 Cookie

```javascript
// 设置 Cookie（键=值; 过期时间; 路径）
document.cookie = 'username=tom; max-age=3600; path=/'

// 读取 Cookie（一次性返回所有 Cookie，需自行解析）
console.log(document.cookie)  // 'username=tom; age=18'

// 封装：获取指定 Cookie
function getCookie(name) {
  const cookies = document.cookie.split('; ')
  for (const item of cookies) {
    const [key, value] = item.split('=')
    if (key === name) return value
  }
  return ''
}

// 删除 Cookie（设置过期时间为过去时间）
document.cookie = 'username=; max-age=-1; path=/'
```

| 特性 | 说明 |
| --- | --- |
| 容量 | 小（约 4KB） |
| 自动携带 | 每次 HTTP 请求自动携带（同源） |
| 过期时间 | 可设置 `max-age` 或 `expires` |
| 操作 | `document.cookie` 读写均通过字符串 |
| 适用场景 | 身份认证、跟踪用户 |

### 5.2 localStorage

```javascript
// 存储（只能存字符串，对象需用 JSON 序列化）
localStorage.setItem('name', 'tom')
localStorage.setItem('user', JSON.stringify({ id: 1, name: 'tom' }))

// 读取
const name = localStorage.getItem('name')           // 'tom'
const user = JSON.parse(localStorage.getItem('user'))  // { id: 1, name: 'tom' }

// 删除指定项
localStorage.removeItem('name')

// 清空所有
localStorage.clear()

// 监听其他标签页的 storage 变化（跨标签页通信）
window.addEventListener('storage', function (e) {
  console.log('storage 变化:', e.key, e.newValue)
})
```

| 特性 | 说明 |
| --- | --- |
| 容量 | 大（约 5MB+） |
| 生命周期 | 永久存储，除非手动清除 |
| 作用域 | 同源共享（所有标签页） |
| API | `setItem` / `getItem` / `removeItem` / `clear` |

### 5.3 sessionStorage

```javascript
// API 与 localStorage 完全一致
sessionStorage.setItem('token', 'abc123')
sessionStorage.getItem('token')
sessionStorage.removeItem('token')
sessionStorage.clear()
```

| 特性 | 说明 |
| --- | --- |
| 容量 | 大（约 5MB+） |
| 生命周期 | 会话级，关闭标签页即清除 |
| 作用域 | 同源 + 同标签页（不同标签页隔离） |
| API | 同 localStorage |

### 5.4 三者对比表

| 对比项 | Cookie | localStorage | sessionStorage |
| --- | --- | --- | --- |
| 容量 | 约 4KB | 约 5MB | 约 5MB |
| 生命周期 | 可设置过期时间 | 永久（手动清除） | 会话级（关闭标签页清除） |
| 作用域 | 同源 + 路径 | 同源（所有标签页共享） | 同源 + 同标签页 |
| 自动随请求发送 | ✅ 是 | ❌ 否 | ❌ 否 |
| API 友好度 | 差（字符串操作） | 好（键值对 API） | 好（键值对 API） |
| 典型场景 | 身份凭证、跟踪 | 长期偏好设置、缓存 | 临时表单数据、单页会话状态 |

⚠️ **易错点**：`localStorage` / `sessionStorage` 只能存字符串，存对象需用 `JSON.stringify` / `JSON.parse` 转换。

---

## 六、日期对象

### 6.1 创建 Date 对象

```javascript
const now = new Date()                    // 当前时间
const date1 = new Date('2024-01-01')      // 指定日期字符串
const date2 = new Date(2024, 0, 1)       // 年、月（0-11）、日
const date3 = new Date(1704067200000)     // 时间戳
```

⚠️ **易错点**：`new Date(2024, 0, 1)` 中月份从 **0 开始**（0=1月，11=12月）。

### 6.2 常用方法

```javascript
const date = new Date()

date.getFullYear()   // 年份，如 2024
date.getMonth()      // 月份（0-11，0 是一月）⚠️ 易错
date.getDate()       // 日（1-31）
date.getDay()        // 星期（0-6，0 是周日）⚠️ 易错
date.getHours()      // 小时（0-23）
date.getMinutes()    // 分钟（0-59）
date.getSeconds()    // 秒（0-59）
date.getMilliseconds() // 毫秒（0-999）

date.getTime()       // 时间戳（毫秒，距 1970-01-01）
```

| 方法 | 返回值 | 注意 |
| --- | --- | --- |
| `getMonth()` | 0-11 | 0 是 1 月，需 +1 |
| `getDay()` | 0-6 | 0 是周日 |
| `getDate()` | 1-31 | 当前月的第几天 |
| `getTime()` | 毫秒时间戳 | 距 1970-01-01 00:00:00 |

⚠️ **易错点**：`getMonth()` 返回 0-11，显示给用户需 +1；`getDay()` 返回 0-6，0 是周日不是周一。

### 6.3 时间戳与格式化

```javascript
// 1. 获取当前时间戳（三种方式，推荐 Date.now()）
console.log(Date.now())           // 推荐，静态方法
console.log(new Date().getTime())
console.log(new Date().valueOf())

// 2. 时间戳转 Date
const date = new Date(Date.now())

// 3. 格式化日期：YYYY-MM-DD HH:mm:ss
function formatDate(date) {
  const Y = date.getFullYear()
  const M = String(date.getMonth() + 1).padStart(2, '0')
  const D = String(date.getDate()).padStart(2, '0')
  const h = String(date.getHours()).padStart(2, '0')
  const m = String(date.getMinutes()).padStart(2, '0')
  const s = String(date.getSeconds()).padStart(2, '0')
  return `${Y}-${M}-${D} ${h}:${m}:${s}`
}
console.log(formatDate(new Date()))  // '2024-07-14 12:30:45'
```

---

## 七、JSON

### 7.1 JSON.stringify()

将 JS 对象/数组转换为 JSON 字符串。

```javascript
const user = { name: 'tom', age: 18, hobbies: ['reading', 'coding'] }

const jsonStr = JSON.stringify(user)
console.log(jsonStr)  // '{"name":"tom","age":18,"hobbies":["reading","coding"]}'

// 第二参数：过滤/转换（数组保留指定字段，函数做转换）
console.log(JSON.stringify(user, ['name', 'age']))  // '{"name":"tom","age":18}'
console.log(JSON.stringify(user, (key, val) => 
  typeof val === 'number' ? undefined : val
))  // '{"name":"tom","hobbies":["reading","coding"]}'

// 第三参数：缩进美化（数字或字符串）
console.log(JSON.stringify(user, null, 2))
// {
//   "name": "tom",
//   "age": 18,
//   "hobbies": [
//     "reading",
//     "coding"
//   ]
// }
```

### 7.2 JSON.parse()

将 JSON 字符串转换为 JS 对象/数组。

```javascript
const jsonStr = '{"name":"tom","age":18}'
const user = JSON.parse(jsonStr)
console.log(user.name)  // 'tom'

// 第二参数：reviver 函数，转换解析结果
const user2 = JSON.parse(jsonStr, (key, val) => {
  if (key === 'age') return val + 1  // 年龄 +1
  return val
})
console.log(user2.age)  // 19
```

### 7.3 注意事项

```javascript
// 1. 不能序列化函数和 undefined（会被忽略或转为 null）
const obj = {
  fn: function () {},  // 函数：被忽略
  und: undefined,      // undefined：被忽略
  sym: Symbol('s'),    // Symbol：被忽略
  nan: NaN,            // NaN：转为 null
  inf: Infinity,       // Infinity：转为 null
  date: new Date()     // Date：转为 ISO 字符串
}
console.log(JSON.stringify(obj))
// '{"nan":null,"inf":null,"date":"2024-07-14T..."}'

// 2. 深拷贝技巧（简单场景，但有局限）
const original = { a: 1, b: { c: 2 } }
const copy = JSON.parse(JSON.stringify(original))
copy.b.c = 999
console.log(original.b.c)  // 2（深拷贝，互不影响）
```

⚠️ **易错点**：`JSON.parse(JSON.stringify(obj))` 实现深拷贝的局限性：
1. 无法拷贝函数、`undefined`、`Symbol`（会被丢弃）
2. `NaN`、`Infinity` 会变成 `null`
3. `Date` 对象会变成字符串
4. `RegExp`、`Error` 会变成空对象
5. 无法处理循环引用（报错）

💡 深拷贝推荐使用 `structuredClone(obj)`（现代浏览器原生支持）或 Lodash 的 `_.cloneDeep`。

---

## 八、正则表达式基础

### 8.1 创建正则

```javascript
// 方式一：字面量（推荐，简洁）
const reg1 = /abc/g

// 方式二：RegExp 构造函数（变量拼接时使用）
const word = 'abc'
const reg2 = new RegExp(word, 'g')

// 区别：字面量无需转义反斜杠，构造函数需要双反斜杠
const reg3 = /\d+/       // 字面量
const reg4 = new RegExp('\\d+')  // 构造函数需转义
```

### 8.2 元字符

| 元字符 | 含义 | 示例 |
| --- | --- | --- |
| `.` | 任意单个字符（除换行符） | `/a.c/` 匹配 `abc`、`a1c` |
| `\d` | 数字 0-9 | `/\d/` 匹配 `5` |
| `\D` | 非数字 | `/\D/` 匹配 `a` |
| `\w` | 字母、数字、下划线 | `/\w/` 匹配 `a_1` |
| `\W` | 非字母数字下划线 | `/\W/` 匹配 `@` |
| `\s` | 空白字符（空格、制表、换行） | `/\s/` 匹配空格 |
| `\S` | 非空白字符 | `/\S/` 匹配 `a` |
| `^` | 字符串开头 | `/^abc/` 匹配以 abc 开头 |
| `$` | 字符串结尾 | `/abc$/` 匹配以 abc 结尾 |
| `[abc]` | 字符集合，匹配其中任意一个 | `/[aeiou]/` 匹配元音 |
| `[^abc]` | 取反，匹配非 a/b/c | `/[^0-9]/` 匹配非数字 |
| `|` | 或 | `/cat\|dog/` 匹配 cat 或 dog |
| `()` | 分组，捕获匹配内容 | `/(ab)+/` 匹配 ab、abab |

### 8.3 量词

| 量词 | 含义 | 示例 |
| --- | --- | --- |
| `*` | 出现 0 次或多次 | `/a*/` 匹配 `''`、`aaa` |
| `+` | 出现 1 次或多次 | `/a+/` 匹配 `a`、`aaa` |
| `?` | 出现 0 次或 1 次 | `/a?/` 匹配 `''`、`a` |
| `{n}` | 出现恰好 n 次 | `/\d{4}/` 匹配 4 位数字 |
| `{n,}` | 至少 n 次 | `/\d{2,}/` 匹配 2 位及以上数字 |
| `{n,m}` | n 到 m 次 | `/\d{2,4}/` 匹配 2-4 位数字 |

```javascript
// 常见正则示例
const phoneReg = /^1[3-9]\d{9}$/                      // 手机号
const emailReg = /^[\w.-]+@[\w-]+(\.[\w-]+)+$/        // 邮箱
const idCardReg = /^\d{17}[\dXx]$/                    // 身份证
const zipCodeReg = /^\d{6}$/                          // 邮编
const urlReg = /^https?:\/\/[\w.-]+(:\d+)?(\/.*)?$/   // URL
```

### 8.4 修饰符

| 修饰符 | 含义 | 示例 |
| --- | --- | --- |
| `g` | 全局匹配（找到所有，否则只找第一个） | `/abc/g` |
| `i` | 忽略大小写 | `/abc/i` 匹配 `ABC` |
| `m` | 多行匹配（`^`/`$` 匹配每行开头/结尾） | `/^abc/gm` |
| `s` | 让 `.` 匹配换行符 | `/a.b/s` 匹配 `a\nb` |

```javascript
const str = 'Hello hello HELLO'
console.log(str.match(/hello/gi))  // ['Hello', 'hello', 'HELLO']
```

### 8.5 正则方法

```javascript
const str = 'Hello World 123'
const reg = /\d+/g

// 1. reg.test(str)：是否匹配，返回 boolean
console.log(reg.test(str))  // true

// 2. reg.exec(str)：返回匹配结果数组（含分组信息），无匹配返回 null
console.log(reg.exec(str))  // ['123', index: 12, input: 'Hello World 123']

// 3. str.match(reg)：返回所有匹配（配合 g 修饰符）
console.log(str.match(reg))  // ['123']

// 4. str.replace(reg, newStr)：替换匹配内容
console.log(str.replace(/\d+/, 'NUM'))     // 'Hello World NUM'
console.log(str.replace(/\d+/g, 'NUM'))    // 全局替换

// 5. str.split(reg)：按正则分割
console.log('a,b;c.d'.split(/[,.;]/))  // ['a', 'b', 'c', 'd']

// 6. str.search(reg)：返回首次匹配的索引，无则 -1
console.log(str.search(/\d/))  // 12
```

| 方法 | 调用者 | 返回值 | 说明 |
| --- | --- | --- | --- |
| `test()` | 正则 | boolean | 判断是否匹配 |
| `exec()` | 正则 | 数组 / null | 返回详细信息（含分组） |
| `match()` | 字符串 | 数组 / null | 配合 `g` 返回所有匹配 |
| `replace()` | 字符串 | 新字符串 | 替换 |
| `split()` | 字符串 | 数组 | 按正则分割 |
| `search()` | 字符串 | 索引 / -1 | 查找首次匹配位置 |

⚠️ **易错点**：
- `match` 配合 `g` 修饰符返回所有匹配的数组（不含分组信息），不配合 `g` 只返回第一个匹配（含分组信息）。
- `replace` 不加 `g` 只替换第一个匹配项。

---

## 💡 关联面试题

**Q1：addEventListener 和 onclick 的区别？**
- `onclick` 同一元素同一事件只能绑定一个，后写覆盖前写；`addEventListener` 可绑定多个，按顺序执行
- `onclick` 不支持事件流控制；`addEventListener` 第三参数可控制捕获/冒泡
- `onclick` 用 `element.onclick = null` 移除；`addEventListener` 用 `removeEventListener`（需同一函数引用）
- 推荐使用 `addEventListener`

**Q2：事件冒泡和事件捕获是什么？如何阻止？**
- 事件冒泡：事件由内向外传播（子元素 → 父元素 → document），是默认阶段
- 事件捕获：事件由外向内传播（document → 父元素 → 子元素）
- 阻止冒泡：`e.stopPropagation()`
- `addEventListener` 第三参数为 `true` 监听捕获阶段，`false`（默认）监听冒泡阶段

**Q3：什么是事件委托？有什么优点？**
- 原理：利用事件冒泡，将子元素的事件统一绑定到父元素上，通过 `e.target` 判断触发源
- 优点：① 减少事件绑定数量，提升性能 ② 动态添加的子元素也能响应事件 ③ 便于统一管理
- 实现：父元素 `addEventListener`，回调中 `if (e.target.tagName === 'XX')` 判断

**Q4：e.target 和 e.currentTarget 的区别？**
- `e.target`：真正触发事件的元素（如点击的那个 `li`）
- `e.currentTarget`：绑定事件监听器的元素（如 `ul`）
- 在事件委托中两者不同，在普通绑定中两者相同

**Q5：localStorage、sessionStorage、Cookie 的区别？**
- 容量：Cookie（4KB） < localStorage / sessionStorage（5MB+）
- 生命周期：Cookie 可设置过期；localStorage 永久；sessionStorage 会话级（关闭标签页清除）
- 作用域：Cookie 同源+路径；localStorage 同源共享所有标签页；sessionStorage 同源+同标签页
- 携带方式：Cookie 随 HTTP 请求自动携带；后两者不携带
- API：Cookie 用字符串操作；后两者用 `setItem`/`getItem` 键值对 API

**Q6：如何实现一个倒计时？（setTimeout vs setInterval）**
- 推荐 `setTimeout` 递归 + 时间戳校准，避免 `setInterval` 因主线程阻塞造成的时间漂移
- 思路：记录结束时间戳 `endTime`，每次用 `endTime - Date.now()` 计算剩余时间，递归调用 `setTimeout`
- `setInterval` 的问题：不保证准时，若回调执行慢，下一次触发会延迟或叠加

**Q7：innerHTML 和 innerText 的区别？**
- `innerHTML`：会解析 HTML 标签，可插入富文本，但有 XSS 风险
- `innerText`：纯文本，不解析标签，受 CSS 影响（隐藏元素读取不到）
- `textContent`：纯文本，包含隐藏元素内容，性能最好（推荐）

**Q8：如何阻止默认行为和事件冒泡？**
- 阻止默认行为：`e.preventDefault()`（如阻止 a 标签跳转、表单提交）
- 阻止事件冒泡：`e.stopPropagation()`
- 两者返回值均为 `undefined`，需在事件处理函数中显式调用
