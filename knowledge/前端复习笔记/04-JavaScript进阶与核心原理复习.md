# JavaScript 进阶与核心原理复习

> 本文档整合 JS 面试原理课内容并补齐缺失核心知识点，涵盖作用域、闭包、原型链、this、继承、深浅拷贝、事件循环、防抖节流、柯里化等高频面试考点。

## 一、作用域与作用域链

### 1.1 作用域类型

| 类型 | 说明 | 声明方式 |
| --- | --- | --- |
| 全局作用域 | 最外层，整个脚本可访问 | 顶层声明的变量 |
| 函数作用域 | 函数内部，外部无法访问 | 函数内声明的变量 |
| 块级作用域 | `{}` 内部，ES6 新增 | `let` / `const` 声明 |

```javascript
// 全局作用域
var globalVar = '全局'

function fn() {
  // 函数作用域
  var functionVar = '函数内'
  
  if (true) {
    // 块级作用域
    let blockVar = '块内'
    console.log(blockVar) // '块内'
  }
  // console.log(blockVar) // 报错：blockVar is not defined
}
```

### 1.2 作用域链

函数嵌套时，内层函数访问变量会先在自身作用域查找，找不到则沿**作用域链**向外层查找，直到全局作用域。

```javascript
let a = '全局'
function outer() {
  let b = '外层'
  function inner() {
    let c = '内层'
    console.log(a, b, c) // 沿作用域链逐层查找
  }
  inner()
}
```

### 1.3 变量提升

`var` 声明的变量和 `function` 声明的函数会在代码执行前被提升到作用域顶部。

```javascript
console.log(a) // undefined（已声明，未赋值）
var a = 10

console.log(b) // 报错：Cannot access 'b' before initialization（暂时性死区）
let b = 20
```

> ⚠️ `let` / `const` 也有提升，但存在**暂时性死区（TDZ）**，在声明前访问会报错。

---

## 二、闭包（重点）

### 2.1 什么是闭包

**闭包**是指有权访问另一个函数作用域中变量的函数。即：函数内部定义的函数，可以访问外部函数的局部变量。

```javascript
function outer() {
  let count = 0
  function inner() {
    count++
    console.log(count)
  }
  return inner
}

const counter = outer()
counter() // 1
counter() // 2
// outer 执行完毕后，count 不会被回收，因为 inner 仍引用它
```

### 2.2 闭包的作用

1. **延长变量的生命周期**：使局部变量在函数执行完后仍保留在内存中
2. **创建私有变量**：外部无法直接访问，只能通过闭包提供的方法操作
3. **实现模块化**：封装私有属性和方法，暴露公共接口

```javascript
// 经典应用：计数器模块
function createCounter() {
  let count = 0 // 私有变量
  return {
    increment() { count++ },
    decrement() { count-- },
    getCount() { return count }
  }
}

const counter = createCounter()
counter.increment()
counter.increment()
console.log(counter.getCount()) // 2
// counter.count // undefined，无法直接访问
```

### 2.3 闭包的注意点

> ⚠️ 闭包会占用内存，变量不会被垃圾回收。过度使用可能导致**内存泄漏**。不再需要时应将闭包置为 `null`。

### 2.4 经典闭包面试题

```javascript
// 经典：for 循环 + setTimeout
for (var i = 1; i <= 3; i++) {
  setTimeout(() => {
    console.log(i) // 4 4 4
  }, 1000)
}

// 解决方式一：let
for (let i = 1; i <= 3; i++) {
  setTimeout(() => {
    console.log(i) // 1 2 3
  }, 1000)
}

// 解决方式二：闭包（IIFE）
for (var i = 1; i <= 3; i++) {
  (function (j) {
    setTimeout(() => {
      console.log(j) // 1 2 3
    }, 1000)
  })(i)
}
```

---

## 三、原型与原型链（重点）

### 3.1 原型对象 prototype

每个**函数**都有一个 `prototype` 属性，指向一个对象（原型对象）。原型对象的用途是包含所有实例共享的属性和方法。

```javascript
function Person(name) {
  this.name = name
}

// 原型上添加方法，所有实例共享
Person.prototype.sayHi = function () {
  console.log(`你好，我是${this.name}`)
}

const p1 = new Person('张三')
const p2 = new Person('李四')
p1.sayHi() // 你好，我是张三
p2.sayHi() // 你好，我是李四
console.log(p1.sayHi === p2.sayHi) // true（共享同一方法）
```

### 3.2 构造函数、原型、实例的关系

```
构造函数 Person
  ├── prototype ──→ 原型对象 Person.prototype
  │                    ├── constructor ──→ Person（指回构造函数）
  │                    └── sayHi()（共享方法）
  │
  └── new Person() ──→ 实例 p1
                         └── __proto__ ──→ Person.prototype
```

### 3.3 `__proto__` 与 prototype 的区别

| 属性 | 所属 | 指向 |
| --- | --- | --- |
| `prototype` | 函数 | 原型对象 |
| `__proto__` | 所有对象 | 自身的原型对象（即构造函数的 prototype） |

```javascript
console.log(p1.__proto__ === Person.prototype) // true
console.log(Person.prototype.constructor === Person) // true
```

### 3.4 原型链

访问对象属性时，先在对象自身查找，找不到则沿 `__proto__` 向上查找，直到 `Object.prototype`，再往上就是 `null`。这条链就是**原型链**。

```javascript
// 原型链：p1 → Person.prototype → Object.prototype → null
console.log(p1.__proto__ === Person.prototype) // true
console.log(Person.prototype.__proto__ === Object.prototype) // true
console.log(Object.prototype.__proto__) // null
```

### 3.5 原型链终点

```javascript
console.log(Object.prototype.__proto__) // null
```

> ⚠️ 原型链的终点是 `null`，不是 `Object.prototype`。`Object.prototype` 是原型链的最后一个非 null 节点。

### 3.6 instanceof 原理

`instanceof` 沿对象的原型链查找，看是否存在构造函数的 `prototype`。

```javascript
console.log(p1 instanceof Person) // true
console.log(p1 instanceof Object) // true
console.log(p1 instanceof Array) // false
```

---

## 四、this 指向（面试重点）

### 4.1 this 的确认规则

| 调用方式 | this 指向 | 示例 |
| --- | --- | --- |
| 全局环境 | window（非严格）/ undefined（严格） | `console.log(this)` |
| 普通函数调用 | window（非严格）/ undefined（严格） | `fn()` |
| 对象方法调用 | 调用者（对象本身） | `obj.fn()` |
| 构造函数调用 | 新创建的实例对象 | `new Fn()` |
| 箭头函数 | 继承外层作用域的 this | `() => {}` |
| 事件绑定 | 绑定事件的元素 | `btn.onclick = fn` |

```javascript
// 1. 普通调用
function fn() {
  console.log(this) // window（非严格模式）
}
fn()

// 2. 对象方法调用
const obj = {
  name: 'jack',
  sayHi() {
    console.log(this) // obj
  }
}
obj.sayHi()

// 3. 构造函数
function Person(name) {
  this.name = name // this 指向新实例
  console.log(this)
}
new Person('rose')

// 4. 箭头函数
const obj2 = {
  name: 'tom',
  sayHi() {
    const inner = () => {
      console.log(this) // obj2（继承 sayHi 的 this）
    }
    inner()
  }
}
obj2.sayHi()
```

### 4.2 改变 this 指向

| 方法 | 参数 | 是否立即执行 | 返回值 |
| --- | --- | --- | --- |
| `call(thisArg, arg1, arg2, ...)` | this + 参数列表 | 是 | 函数执行结果 |
| `apply(thisArg, [argsArray])` | this + 参数数组 | 是 | 函数执行结果 |
| `bind(thisArg, arg1, arg2, ...)` | this + 参数列表 | 否 | 绑定 this 的新函数 |

```javascript
function func(p1, p2) {
  console.log(this, p1, p2)
}

const obj = { name: 'jack' }

func.call(obj, 1, 2)    // {name:'jack'} 1 2
func.apply(obj, [1, 2]) // {name:'jack'} 1 2
const bound = func.bind(obj, 1)
bound(2)                 // {name:'jack'} 1 2
```

### 4.3 手写 call / apply / bind

```javascript
// 手写 myCall
Function.prototype.myCall = function (thisArg, ...args) {
  const fn = Symbol()           // 用 Symbol 避免属性冲突
  thisArg[fn] = this            // 将函数设为对象的属性
  const res = thisArg[fn](...args) // 通过对象方法调用，this 指向 thisArg
  delete thisArg[fn]            // 删除临时属性
  return res
}

// 手写 myApply
Function.prototype.myApply = function (thisArg, args) {
  const fn = Symbol()
  thisArg[fn] = this
  const res = thisArg[fn](...args)
  delete thisArg[fn]
  return res
}

// 手写 myBind
Function.prototype.myBind = function (thisArg, ...args) {
  return (...args2) => {
    return this.call(thisArg, ...args, ...args2)
  }
}
```

---

## 五、继承

### 5.1 ES5 继承方式

| 方式 | 核心 | 缺点 |
| --- | --- | --- |
| 原型链继承 | `Son.prototype = new Parent()` | 引用类型被所有实例共享 |
| 构造函数继承 | `Parent.call(this)` | 无法继承原型上的方法 |
| 组合继承 | 原型链 + 构造函数 | 调用两次父类构造函数 |
| 原型式继承 | `Object.create(obj)` | 引用类型被共享 |
| 寄生式继承 | 原型式 + 增强方法 | 方法无法复用 |
| **寄生组合式继承** | 构造函数 + 原型副本 | **最优方案** |

```javascript
// 寄生组合式继承（ES5 最优方案）
function inheritPrototype(son, parent) {
  const prototype = Object.create(parent.prototype) // 基于父类原型创建副本
  prototype.constructor = son                        // 修正 constructor
  son.prototype = prototype
}

function Parent(name) {
  this.name = name
  this.foods = ['西蓝花', '西红柿']
}
Parent.prototype.sayHi = function () {
  console.log(`你好，我是${this.name}`)
}

function Son(name, age) {
  Parent.call(this, name) // 继承属性
  this.age = age
}
inheritPrototype(Son, Parent) // 继承方法
```

### 5.2 ES6 class 继承

```javascript
class Person {
  #secret = '私有属性'  // 私有属性
  static info = '静态属性' // 静态属性

  constructor(name, food) {
    this.name = name
    this.food = food
  }
  
  sayHi() {
    console.log(`你好，我是${this.name}`)
  }
  
  static staticMethod() {  // 静态方法
    console.log('静态方法，this 指向类本身')
  }
}

class Student extends Person {
  constructor(name, food, song) {
    super(name, food) // 必须在 this 之前调用
    this.song = song
  }
  
  sing() {
    console.log(`${this.name} 唱 ${this.song}`)
  }
}

const s = new Student('李雷', '花菜', '孤勇者')
s.sayHi()  // 继承自父类
s.sing()
Person.staticMethod() // 静态方法通过类调用
```

> ⚠️ `class` 本质是 ES5 继承的**语法糖**，但写法更清晰。子类构造函数中使用 `this` 前必须先调用 `super()`。

---

## 六、深拷贝与浅拷贝（补齐）

### 6.1 浅拷贝

只拷贝第一层，嵌套的引用类型仍共享地址。

| 方式 | 说明 |
| --- | --- |
| `Object.assign({}, obj)` | 浅拷贝对象 |
| `{ ...obj }` | 展开运算符浅拷贝 |
| `Array.from(arr)` / `[...arr]` | 浅拷贝数组 |
| `arr.concat()` / `arr.slice()` | 浅拷贝数组 |

```javascript
const obj = { a: 1, b: { c: 2 } }
const shallow = { ...obj }
shallow.a = 10
shallow.b.c = 20
console.log(obj.a)   // 1（基本类型不受影响）
console.log(obj.b.c) // 20（引用类型被修改！）
```

### 6.2 深拷贝

递归拷贝所有层级，完全独立。

```javascript
// 方式一：JSON（简单但有局限）
const deep1 = JSON.parse(JSON.stringify(obj))
// 缺点：无法处理 function、undefined、Symbol、循环引用、Date、RegExp

// 方式二：递归实现（基础版）
function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj
  if (obj instanceof Date) return new Date(obj)
  if (obj instanceof RegExp) return new RegExp(obj)
  
  const clone = Array.isArray(obj) ? [] : {}
  for (let key in obj) {
    if (obj.hasOwnProperty(key)) {
      clone[key] = deepClone(obj[key]) // 递归拷贝
    }
  }
  return clone
}

// 方式三：structuredClone（原生 API，推荐）
const deep2 = structuredClone(obj)
// 支持循环引用、Date、RegExp 等，不支持 function 和 DOM 节点
```

---

## 七、事件循环 Event Loop（补齐）

### 7.1 同步与异步

- **同步任务**：在主线程上排队执行的任务
- **异步任务**：不进入主线程，进入任务队列的任务

### 7.2 宏任务与微任务

| 类型 | 常见 API |
| --- | --- |
| 宏任务（MacroTask） | setTimeout、setInterval、I/O、UI 渲染 |
| 微任务（MicroTask） | Promise.then/catch/finally、MutationObserver、queueMicrotask |

> ⚠️ 微任务优先级**高于**宏任务。每执行完一个宏任务，会清空所有微任务队列。

### 7.3 执行流程

```
1. 执行同步代码（主线程任务）
2. 执行栈清空后，检查微任务队列，全部执行
3. 微任务清空后，执行一个宏任务
4. 回到步骤 2，循环往复
```

### 7.4 经典面试题

```javascript
console.log(1)                          // 同步

setTimeout(() => {
  console.log(2)                        // 宏任务
}, 0)

Promise.resolve().then(() => {
  console.log(3)                        // 微任务
})

console.log(4)                          // 同步

// 输出顺序：1 → 4 → 3 → 2
```

```javascript
// 复杂示例
async function async1() {
  console.log('async1 start')           // 同步
  await async2()
  console.log('async1 end')             // 微任务（await 后面的代码相当于 .then）
}
async function async2() {
  console.log('async2')                 // 同步
}

console.log('script start')             // 同步
async1()
console.log('script end')               // 同步

// 输出：script start → async1 start → async2 → script end → async1 end
```

> ⚠️ `async/await` 中，`await` 之后的代码等价于放在 `.then()` 中，属于微任务。

---

## 八、防抖与节流

### 8.1 防抖（Debounce）

**连续触发后，只在最后一次停止后的指定时间执行一次。**

适用场景：搜索输入框、窗口 resize、表单验证

```javascript
function debounce(fn, delay) {
  let timer = null
  return function (...args) {
    clearTimeout(timer) // 清除上一次的定时器
    timer = setTimeout(() => {
      fn.apply(this, args)
    }, delay)
  }
}

// 使用
input.addEventListener('input', debounce(function (e) {
  console.log('搜索：', this.value)
}, 500))
```

### 8.2 节流（Throttle）

**连续触发时，每隔指定时间执行一次。**

适用场景：滚动加载、按钮防重复点击、鼠标拖拽

```javascript
function throttle(fn, interval) {
  let lastTime = 0
  return function (...args) {
    const now = Date.now()
    if (now - lastTime >= interval) {
      fn.apply(this, args)
      lastTime = now
    }
  }
}

// 使用
window.addEventListener('scroll', throttle(function () {
  console.log('滚动位置：', window.scrollY)
}, 200))
```

### 8.3 防抖 vs 节流

| 对比 | 防抖 | 节流 |
| --- | --- | --- |
| 核心 | 只执行最后一次 | 固定频率执行 |
| 比喻 | 电梯没人了才关门 | 电梯每 5 分钟走一次 |
| 场景 | 搜索框、resize | 滚动、拖拽 |

---

## 九、函数柯里化（Currying）

### 9.1 什么是柯里化

将接受多个参数的函数，转换为接受单一参数并返回新函数的技术。

```javascript
// 普通函数
function add(a, b, c) {
  return a + b + c
}

// 柯里化后
function curriedAdd(a) {
  return function (b) {
    return function (c) {
      return a + b + c
    }
  }
}

console.log(add(1, 2, 3))         // 6
console.log(curriedAdd(1)(2)(3))  // 6
```

### 9.2 通用柯里化实现

```javascript
function curry(fn) {
  return function curried(...args) {
    // 参数足够时执行原函数
    if (args.length >= fn.length) {
      return fn.apply(this, args)
    }
    // 参数不足时返回新函数继续收集
    return function (...args2) {
      return curried.apply(this, [...args, ...args2])
    }
  }
}

const curriedAdd = curry(add)
console.log(curriedAdd(1, 2, 3))    // 6
console.log(curriedAdd(1)(2)(3))    // 6
console.log(curriedAdd(1, 2)(3))    // 6
```

### 9.3 柯里化的意义

1. **参数复用**：固定部分参数，生成新函数
2. **延迟执行**：参数收集够了才执行
3. **函数组合**：配合其他高阶函数使用

---

## 十、手写 Promise（核心原理）

### 10.1 Promise 核心结构

```javascript
const PENDING = 'pending'
const FULFILLED = 'fulfilled'
const REJECTED = 'rejected'

class MyPromise {
  constructor(executor) {
    this.state = PENDING
    this.value = undefined
    this.reason = undefined
    this.onFulfilledCallbacks = [] // 存储成功回调
    this.onRejectedCallbacks = []  // 存储失败回调

    const resolve = (value) => {
      if (this.state === PENDING) {
        this.state = FULFILLED
        this.value = value
        this.onFulfilledCallbacks.forEach(fn => fn())
      }
    }

    const reject = (reason) => {
      if (this.state === PENDING) {
        this.state = REJECTED
        this.reason = reason
        this.onRejectedCallbacks.forEach(fn => fn())
      }
    }

    try {
      executor(resolve, reject) // 立即执行
    } catch (err) {
      reject(err)
    }
  }

  then(onFulfilled, onRejected) {
    onFulfilled = typeof onFulfilled === 'function' ? onFulfilled : v => v
    onRejected = typeof onRejected === 'function' ? onRejected : e => { throw e }

    const promise2 = new MyPromise((resolve, reject) => {
      const fulfilledTask = () => {
        queueMicrotask(() => {
          try {
            const x = onFulfilled(this.value)
            resolvePromise(promise2, x, resolve, reject)
          } catch (err) {
            reject(err)
          }
        })
      }

      const rejectedTask = () => {
        queueMicrotask(() => {
          try {
            const x = onRejected(this.reason)
            resolvePromise(promise2, x, resolve, reject)
          } catch (err) {
            reject(err)
          }
        })
      }

      if (this.state === FULFILLED) {
        fulfilledTask()
      } else if (this.state === REJECTED) {
        rejectedTask()
      } else {
        this.onFulfilledCallbacks.push(fulfilledTask)
        this.onRejectedCallbacks.push(rejectedTask)
      }
    })

    return promise2 // 实现链式调用
  }

  catch(onRejected) {
    return this.then(null, onRejected)
  }

  finally(callback) {
    return this.then(
      value => MyPromise.resolve(callback()).then(() => value),
      reason => MyPromise.resolve(callback()).then(() => { throw reason })
    )
  }

  // 静态方法
  static resolve(value) {
    if (value instanceof MyPromise) return value
    return new MyPromise(resolve => resolve(value))
  }

  static reject(reason) {
    return new MyPromise((_, reject) => reject(reason))
  }

  static all(promises) {
    return new MyPromise((resolve, reject) => {
      const results = []
      let count = 0
      promises.forEach((p, index) => {
        MyPromise.resolve(p).then(res => {
          results[index] = res
          if (++count === promises.length) resolve(results)
        }, reject)
      })
    })
  }

  static race(promises) {
    return new MyPromise((resolve, reject) => {
      promises.forEach(p => {
        MyPromise.resolve(p).then(resolve, reject)
      })
    })
  }
}

// 处理 then 返回值为 Promise 的情况
function resolvePromise(promise2, x, resolve, reject) {
  if (promise2 === x) {
    return reject(new TypeError('Chaining cycle detected'))
  }
  if (x instanceof MyPromise) {
    x.then(resolve, reject)
  } else {
    resolve(x)
  }
}
```

### 10.2 Promise 静态方法对比

| 方法 | 说明 | 全部成功 | 有失败 |
| --- | --- | --- | --- |
| `Promise.all` | 全部完成 | 返回所有结果的数组 | 第一个失败的 reason |
| `Promise.race` | 第一个完成 | 第一个的结果 | 第一个的 reason |
| `Promise.allSettled` | 全部结束 | 返回 {status, value/reason} 数组 | 不会 reject |
| `Promise.any` | 第一个成功 | 第一个成功的结果 | 全部失败才 reject |

---

## 十一、递归（补齐）

### 11.1 递归概念

函数内部调用自身，必须有**终止条件**，否则会栈溢出。

```javascript
// 经典：阶乘
function factorial(n) {
  if (n <= 1) return 1     // 终止条件
  return n * factorial(n - 1) // 递归调用
}

// 经典：斐波那契数列
function fibonacci(n) {
  if (n <= 1) return n
  return fibonacci(n - 1) + fibonacci(n - 2)
}
```

### 11.2 递归应用

```javascript
// 1. 深拷贝（见第六节）
// 2. 扁平化数组
function flatten(arr) {
  const result = []
  arr.forEach(item => {
    if (Array.isArray(item)) {
      result.push(...flatten(item)) // 递归展开
    } else {
      result.push(item)
    }
  })
  return result
}
console.log(flatten([1, [2, [3, [4]]]])) // [1, 2, 3, 4]

// 3. 树形结构遍历
function traverseTree(node, callback) {
  callback(node)
  if (node.children) {
    node.children.forEach(child => traverseTree(child, callback))
  }
}
```

---

## 💡 关联面试题

**Q1：什么是闭包？应用场景有哪些？**
- 闭包是能访问其他函数作用域变量的函数
- 应用：计数器、私有变量、模块化、防抖节流、柯里化
- 注意：会导致变量不被回收，注意内存泄漏

**Q2：说说原型链？**
- 每个对象有 `__proto__` 指向其原型对象，原型对象也有 `__proto__`，层层向上直到 `null`，形成原型链
- 属性查找时沿原型链查找，找不到返回 undefined
- `Object.prototype` 是所有对象的根原型，其 `__proto__` 为 `null`

**Q3：如何确定 this 的指向？**
- 全局/普通调用：window（严格模式 undefined）
- 对象方法：调用者
- 构造函数：new 创建的实例
- 箭头函数：继承外层 this
- call/apply/bind：手动指定

**Q4：call、apply、bind 的区别？**
- call：参数列表，立即执行
- apply：参数数组，立即执行
- bind：参数列表，返回新函数，不立即执行

**Q5：ES5 继承有哪些方式？最优方案是什么？**
- 原型链、构造函数、组合、原型式、寄生式、寄生组合式
- 最优：寄生组合式继承（构造函数继承属性 + 原型副本继承方法，避免调用两次父类构造函数）

**Q6：深拷贝和浅拷贝的区别？如何实现深拷贝？**
- 浅拷贝只复制第一层，引用类型仍共享地址
- 深拷贝递归复制所有层级，完全独立
- 实现：`JSON.parse(JSON.stringify())`、递归、`structuredClone()`

**Q7：说说事件循环机制？**
- JS 是单线程，通过事件循环处理异步
- 执行流程：同步代码 → 微任务队列（全部清空）→ 一个宏任务 → 微任务 → 循环
- 微任务：Promise.then、MutationObserver
- 宏任务：setTimeout、setInterval

**Q8：防抖和节流的区别？分别适用什么场景？**
- 防抖：连续触发只执行最后一次 → 搜索框、resize
- 节流：固定频率执行 → 滚动、拖拽

**Q9：什么是函数柯里化？**
- 将多参数函数转换为单参数函数链
- 作用：参数复用、延迟执行、函数组合

**Q10：手写 Promise 的关键点是什么？**
- 三种状态（pending/fulfilled/rejected）不可逆
- then 返回新 Promise 实现链式调用
- 异步回调需用微任务（queueMicrotask）
- 处理 then 返回值为 Promise 的情况
